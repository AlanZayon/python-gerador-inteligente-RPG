"""Play Application: BookIndex lookup + Roll Call confirmation."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models.entities import Campaign, CampaignCharacter, Job, User
from services.play.gm import ActionError, MockGMLLM, confirm_roll, submit_player_action
from services.play.gm.mock_llm import LLMTurn
from services.play.gm.rag_context import retrieve_gm_rules
from services.play.gm.roll_call_speech import ensure_spoken_roll_call, scrub_roll_wait_meta
from services.play.gm.state import dump_state, load_state
from services.play.sessions import (
    claim_character,
    create_game_session,
    join_game_session,
    set_ready,
    start_game_session,
)
from services.play.sync import get_reconnect_snapshot


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
    monkeypatch.setattr("services.play.sync.SessionLocal", Session)
    monkeypatch.setenv("VOICE_TTS_PROVIDER", "mock")
    monkeypatch.setenv("VOICE_STT_PROVIDER", "mock")

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
        id="job-roll",
        user_id=host.id,
        status="completed",
        blueprint_json=json.dumps({"title": "Salt", "premise": "Storms gather."}),
        book_id="bk_roll",
        system_preset="dnd5e",
        campaign_s3_key="c.md",
    )
    db.add(job)
    db.commit()
    campaign = Campaign(
        job_id=job.id,
        host_user_id=host.id,
        book_id="bk_roll",
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
            sheet_json=json.dumps(
                {"name": name, "class": "Rogue", "abilities": "DEX 16", "raw_excerpt": "Stealth +5"}
            ),
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

    payload = {
        "Session": Session,
        "host": host,
        "p2": p2,
        "chars": chars,
        "session_id": gs.id,
        "campaign": campaign,
    }
    db.close()
    yield payload


def _climb_retrieve(*, book_id, query, top_k=None, **_):
    return [
        {"text": "Climbing is an Athletics check against DC 12.", "score": 0.9, "id": "c1"},
        {"text": "Never invent a roll total; the table rolls.", "score": 0.8, "id": "c2"},
    ]


def test_scrub_strips_waiting_aside_and_speaks_the_call():
    raw = (
        "O homem avança a passos firmes. "
        "*(Aguardando a rolagem de Sabedoria (Percepção) solicitada ao jogador).*"
    )
    pending = {
        "skill": "Sabedoria (Percepção)",
        "notation": "1d20+3",
        "dc": 13,
    }
    out = ensure_spoken_roll_call(
        raw, pending, character_name="Kael", language="en"
    )
    assert "Aguardando" not in out
    assert "aguardando" not in out.lower()
    assert "solicitada" not in out.lower()
    assert "faça um teste de Sabedoria (Percepção)" in out
    assert "make a" not in out.lower()
    assert "1d20+3" in out
    assert "CD 13" in out
    assert "O homem avança" in out
    assert "firmes. Kael" in out
    assert "*" not in out


def test_scrub_roll_wait_meta_alone():
    cleaned = scrub_roll_wait_meta(
        "A tocha treme. *(waiting for the player to roll Perception).*"
    )
    assert "waiting" not in cleaned.lower()
    assert "tocha" in cleaned.lower()


def test_load_state_preserves_pending_check():
    raw = dump_state(
        {
            "scene": "Harbor",
            "pending_check": {"id": "pc1", "skill": "Athletics", "notation": "1d20"},
        }
    )
    loaded = load_state(raw)
    assert loaded["pending_check"]["id"] == "pc1"
    assert loaded["pending_check"]["skill"] == "Athletics"


def test_lookup_rules_is_scoped_not_full_book(live_table):
    seen = {}

    def fake_retrieve(*, book_id, query, top_k=None, **_):
        seen["book_id"] = book_id
        seen["query"] = query
        seen["top_k"] = top_k
        return _climb_retrieve(book_id=book_id, query=query, top_k=top_k)

    excerpts = retrieve_gm_rules(
        book_id="bk_roll",
        player_action="I climb the mast",
        scene="Harbor",
        character_name="Mira",
        system_preset="dnd5e",
        top_k=3,
        retrieve_fn=fake_retrieve,
    )
    assert seen["book_id"] == "bk_roll"
    assert seen["top_k"] == 3
    assert "climb" in seen["query"].lower() or "Harbor" in seen["query"]
    assert "ability checks" in seen["query"].lower() or "Dungeons" in seen["query"]
    assert len(excerpts) == 2
    assert "full book" not in json.dumps(excerpts).lower()


def test_climb_issues_roll_call_without_rolling(live_table):
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I climb the mast",
        llm=MockGMLLM(),
        retrieve_fn=_climb_retrieve,
        dice_rng=lambda sides: 99,
    )
    pending = result["state"]["pending_check"]
    assert pending
    assert pending["skill"] == "Athletics"
    assert result["state"]["last_dice"] is None
    assert any(t["name"] == "lookup_rules" for t in result["tool_results"])
    assert any(t["name"] == "request_roll" for t in result["tool_results"])
    assert not any(t["name"] == "roll_dice" for t in result["tool_results"])
    lookup = next(t for t in result["tool_results"] if t["name"] == "lookup_rules")
    texts = json.dumps(lookup["result"])
    assert "Climbing is an Athletics" in texts
    assert "full book" not in texts.lower()
    assert any(e["type"] == "roll_requested" for e in result["events"])
    assert "Athletics" in result["narration"]
    assert "check" in result["narration"].lower() or "teste" in result["narration"].lower()
    assert "table waits" not in result["narration"].lower()
    assert "aguardando" not in result["narration"].lower()


def test_other_player_blocked_while_roll_call_pending(live_table):
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I climb the mast",
        llm=MockGMLLM(),
        retrieve_fn=_climb_retrieve,
    )
    with pytest.raises(ActionError) as exc:
        submit_player_action(
            live_table["p2"].id,
            live_table["session_id"],
            "I watch the dock.",
            llm=MockGMLLM(),
        )
    assert exc.value.code == "awaiting_roll"


def test_wrong_player_cannot_confirm_roll(live_table):
    called = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I climb the mast",
        llm=MockGMLLM(),
        retrieve_fn=_climb_retrieve,
    )
    pending_id = called["state"]["pending_check"]["id"]
    with pytest.raises(ActionError) as exc:
        confirm_roll(
            live_table["p2"].id,
            live_table["session_id"],
            pending_id=pending_id,
            llm=MockGMLLM(),
        )
    assert exc.value.code == "forbidden"
    snap = get_reconnect_snapshot(live_table["host"].id, live_table["session_id"])
    assert snap["state"]["pending_check"]["id"] == pending_id


def test_target_confirms_roll_clears_pending_and_narrates(live_table):
    called = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I climb the mast",
        llm=MockGMLLM(),
        retrieve_fn=_climb_retrieve,
    )
    pending_id = called["state"]["pending_check"]["id"]
    result = confirm_roll(
        live_table["host"].id,
        live_table["session_id"],
        pending_id=pending_id,
        llm=MockGMLLM(),
        dice_rng=lambda sides: 17,
    )
    assert result["state"]["pending_check"] is None
    assert result["state"]["last_dice"]["total"] == 17
    assert result["state"]["last_dice"]["rolls"] == [17]
    assert "17" in result["narration"]
    assert not any(t["name"] == "request_roll" for t in result["tool_results"])
    assert any(t["name"] == "confirm_roll" for t in result["tool_results"])


def test_reconnect_snapshot_includes_roll_call(live_table):
    called = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I climb the mast",
        llm=MockGMLLM(),
        retrieve_fn=_climb_retrieve,
    )
    pending_id = called["state"]["pending_check"]["id"]
    snap = get_reconnect_snapshot(live_table["p2"].id, live_table["session_id"], after_seq=0)
    assert snap["state"]["pending_check"]["id"] == pending_id
    assert any(e["type"] == "roll_requested" for e in snap["events"])


def test_resolution_does_not_issue_second_roll_call(live_table):
    called = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I climb the mast",
        llm=MockGMLLM(),
        retrieve_fn=_climb_retrieve,
    )
    result = confirm_roll(
        live_table["host"].id,
        live_table["session_id"],
        pending_id=called["state"]["pending_check"]["id"],
        llm=MockGMLLM(),
        dice_rng=lambda sides: 8,
    )
    assert result["state"]["pending_check"] is None
    assert not any(t["name"] == "request_roll" for t in result["tool_results"])


class _OrChoiceLLM:
    """Replay of Ironpeak event 95: one Roll Call mashed two checks."""

    def complete_turn(self, context: dict) -> LLMTurn:
        if context.get("purpose") == "roll_resolution":
            result = context.get("resolved_roll") or {}
            return LLMTurn(
                tool_calls=[],
                narration=f"The {result.get('skill')} check settles on {result.get('total')}.",
            )
        return LLMTurn(
            tool_calls=[
                {
                    "name": "request_roll",
                    "args": {
                        "skill": "Sabedoria (Percepção) ou Destreza (Furtividade)",
                        "notation": "1d20+2",
                        "dc": 12,
                        "reason": "Para manter-se oculto e atento aos movimentos na câmara",
                    },
                }
            ],
            narration="Você se encolhe na penumbra.",
        )


def test_or_roll_call_requires_player_choice(live_table):
    called = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "Permaneço escondido atrás da coluna",
        llm=_OrChoiceLLM(),
    )
    pending = called["state"]["pending_check"]
    alts = pending["alternatives"]
    skills = [a["skill"] for a in alts]
    assert "Sabedoria (Percepção)" in skills
    assert "Destreza (Furtividade)" in skills
    assert "ou" in pending["skill"].lower() or "or" in pending["skill"].lower()

    with pytest.raises(ActionError) as exc:
        confirm_roll(
            live_table["host"].id,
            live_table["session_id"],
            pending_id=pending["id"],
            llm=_OrChoiceLLM(),
        )
    assert exc.value.code == "needs_choice"
    snap = get_reconnect_snapshot(live_table["host"].id, live_table["session_id"])
    assert snap["state"]["pending_check"]["id"] == pending["id"]

    result = confirm_roll(
        live_table["host"].id,
        live_table["session_id"],
        pending_id=pending["id"],
        chosen_skill="Destreza (Furtividade)",
        llm=_OrChoiceLLM(),
        dice_rng=lambda sides: 10,
    )
    assert result["state"]["pending_check"] is None
    assert result["state"]["last_dice"]["skill"] == "Destreza (Furtividade)"
    assert result["state"]["last_dice"]["total"] == 12
    assert "Destreza (Furtividade)" in result["narration"]
