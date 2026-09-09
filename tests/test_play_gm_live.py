"""Play Application: live 9router GM + scoped RAG (mock remains default)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models.entities import Campaign, CampaignCharacter, Job, User
from services.play.gm import MockGMLLM, submit_player_action
from services.play.gm.live_llm import LiveGMLLM
from services.play.gm.provider import resolve_gm_llm
from services.play.gm.rag_context import retrieve_gm_rules
from services.play.gm.runtime import run_gm_flight
from services.play.gm.tools import TOOL_NAMES
from services.play.sessions import (
    claim_character,
    create_game_session,
    join_game_session,
    set_ready,
    start_game_session,
)


@pytest.fixture
def live_table(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr("services.play.sessions.SessionLocal", Session)
    monkeypatch.setattr("services.play.gm.runtime.SessionLocal", Session)
    monkeypatch.setattr("services.play.gm.actions.SessionLocal", Session)
    monkeypatch.setattr(
        "services.play.gm.runtime.retrieve_gm_rules",
        lambda **kwargs: [],
    )

    import services.play.gm.actions as actions_mod

    actions_mod._locks.clear()
    actions_mod._queues.clear()

    db = Session()
    host = User(clerk_id="host", email="host@ex.com")
    p2 = User(clerk_id="p2", email="p2@ex.com")
    db.add_all([host, p2])
    db.commit()
    for u in (host, p2):
        db.refresh(u)

    job = Job(
        id="job-live",
        user_id=host.id,
        status="completed",
        blueprint_json=json.dumps({"title": "Salt", "premise": "Storms."}),
        book_id="bk_live",
        campaign_s3_key="c.md",
    )
    db.add(job)
    db.commit()
    campaign = Campaign(
        job_id=job.id,
        host_user_id=host.id,
        book_id="bk_live",
        title="Salt",
        blueprint_json=job.blueprint_json,
        status="ready",
    )
    db.add(campaign)
    db.flush()
    chars = []
    for i, name in enumerate(["Mira", "Joren"]):
        c = CampaignCharacter(
            campaign_id=campaign.id,
            display_name=name,
            sheet_json=json.dumps({"name": name}),
            sort_order=i,
            claimable=True,
        )
        db.add(c)
        chars.append(c)
    db.commit()
    for c in chars:
        db.refresh(c)

    gs = create_game_session(host.id, campaign.id)
    join_game_session(p2.id, gs.invite_code)
    claim_character(host.id, gs.id, chars[0].id)
    claim_character(p2.id, gs.id, chars[1].id)
    set_ready(host.id, gs.id, True)
    set_ready(p2.id, gs.id, True)
    start_game_session(host.id, gs.id)

    yield {
        "Session": Session,
        "host": host,
        "p2": p2,
        "chars": chars,
        "session_id": gs.id,
        "campaign": campaign,
    }
    db.close()


def test_resolve_gm_llm_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("GM_LLM_PROVIDER", raising=False)
    llm = resolve_gm_llm()
    assert isinstance(llm, MockGMLLM)


def test_resolve_gm_llm_live_when_configured(monkeypatch):
    monkeypatch.setenv("GM_LLM_PROVIDER", "9router")
    monkeypatch.setenv("NINEROUTER_KEY", "sk-test-abcdefghijklmnopqrstuv")
    llm = resolve_gm_llm()
    assert isinstance(llm, LiveGMLLM)


class _FakeChat:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("no more fake responses")
        return self.responses.pop(0)


def test_live_llm_executes_validated_tool_calls(live_table, monkeypatch):
    fake = _FakeChat(
        [
            {
                "message": {"role": "assistant", "content": ""},
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "roll_dice",
                        "args": {"notation": "1d20", "reason": "Athletics"},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "model": "my-combo",
                "latency_ms": 12.5,
                "raw": {},
            },
            {
                "message": {"role": "assistant", "content": "The dice settle on 9."},
                "tool_calls": [],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8},
                "model": "my-combo",
                "latency_ms": 8.0,
                "raw": {},
            },
        ]
    )
    monkeypatch.setattr("services.play.gm.live_llm.chat_completion", fake)
    llm = LiveGMLLM(retrieve_fn=lambda **kw: [])
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I roll a d20.",
        llm=llm,
        dice_rng=lambda sides: 9,
    )
    assert any(t["name"] == "roll_dice" for t in result["tool_results"])
    assert result["state"]["last_dice"]["total"] == 9
    assert "9" in result["narration"]
    assert result["observability"]["purpose"] == "gm_turn"
    assert result["observability"]["model"] == "my-combo"
    assert result["observability"]["latency_ms"] >= 0
    assert fake.calls[0].get("tools")


def test_invalid_tool_calls_are_skipped(live_table, monkeypatch):
    fake = _FakeChat(
        [
            {
                "message": {"role": "assistant", "content": "Nothing happens."},
                "tool_calls": [
                    {"id": "bad", "name": "delete_database", "args": {}},
                    {"id": "ok", "name": "create_event", "args": {"type": "note", "payload": {"x": 1}}},
                ],
                "usage": {},
                "model": "my-combo",
                "latency_ms": 1.0,
                "raw": {},
            }
        ]
    )
    monkeypatch.setattr("services.play.gm.live_llm.chat_completion", fake)
    llm = LiveGMLLM(retrieve_fn=lambda **kw: [])
    result = submit_player_action(
        live_table["p2"].id,
        live_table["session_id"],
        "I wait.",
        llm=llm,
    )
    names = [t["name"] for t in result["tool_results"]]
    assert "delete_database" not in names
    assert "create_event" in names
    assert "delete_database" not in TOOL_NAMES


def test_malformed_tool_arguments_are_tolerated(live_table, monkeypatch):
    fake = _FakeChat(
        [
            {
                "message": {"role": "assistant", "content": "You pause."},
                "tool_calls": [
                    {"id": "x", "name": "roll_dice", "args": "not-a-dict"},
                    {"id": "y", "name": "create_event", "args": {"type": "beat", "payload": {}}},
                ],
                "usage": {},
                "model": "my-combo",
                "latency_ms": 1.0,
                "raw": {},
            }
        ]
    )
    monkeypatch.setattr("services.play.gm.live_llm.chat_completion", fake)
    llm = LiveGMLLM(retrieve_fn=lambda **kw: [])
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I hesitate.",
        llm=llm,
    )
    assert result["narration"]
    assert any(t["name"] == "create_event" for t in result["tool_results"])
    assert not any(t["name"] == "roll_dice" for t in result["tool_results"])


def test_rag_retrieval_is_scoped_not_full_book(live_table):
    seen = {}

    def fake_retrieve(*, book_id, query, top_k=None, **_):
        seen["book_id"] = book_id
        seen["query"] = query
        seen["top_k"] = top_k
        return [
            {"text": "Athletics checks use Strength.", "score": 0.9},
            {"text": "Climbing rules.", "score": 0.8},
        ]

    excerpts = retrieve_gm_rules(
        book_id="bk_live",
        player_action="I climb the mast",
        scene="Harbor",
        character_name="Mira",
        top_k=3,
        retrieve_fn=fake_retrieve,
    )
    assert seen["book_id"] == "bk_live"
    assert seen["top_k"] == 3
    assert "Harbor" in seen["query"] or "climb" in seen["query"].lower()
    assert len(excerpts) == 2
    assert "full book" not in json.dumps(excerpts).lower()


def test_runtime_includes_rag_excerpts_in_llm_context(live_table, monkeypatch):
    captured = {}

    class CapturingMock(MockGMLLM):
        def complete_turn(self, context):
            captured["context"] = context
            return super().complete_turn(context)

    monkeypatch.setattr(
        "services.play.gm.runtime.retrieve_gm_rules",
        lambda **kw: [{"text": "Rule excerpt about docks.", "score": 1.0}],
    )
    result = run_gm_flight(
        live_table["session_id"],
        live_table["host"].id,
        live_table["chars"][0].id,
        "I search the docks.",
        llm=CapturingMock(),
    )
    assert result["narration"]
    assert captured["context"]["rules_excerpts"]
    assert "docks" in captured["context"]["rules_excerpts"][0]["text"]
