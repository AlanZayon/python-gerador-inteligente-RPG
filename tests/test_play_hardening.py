"""Play Application: hardening, rate limits, agency, recovery."""

from __future__ import annotations

import json
import logging

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models.entities import Campaign, CampaignCharacter, Job, User
from services.play.gm import ActionError, MockGMLLM, submit_player_action
from services.play.gm.mock_llm import LLMTurn
from services.play.gm.tools import ToolContext, execute_tool
from services.play.sessions import (
    claim_character,
    create_game_session,
    join_game_session,
    set_ready,
    start_game_session,
)
from services.play.sync import get_reconnect_snapshot
from services.rate_limit import clear_memory_rate_limits


@pytest.fixture
def live_table(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    for path in (
        "services.play.sessions.SessionLocal",
        "services.play.gm.runtime.SessionLocal",
        "services.play.gm.actions.SessionLocal",
        "services.play.memory.SessionLocal",
        "services.play.sync.SessionLocal",
    ):
        monkeypatch.setattr(path, Session)
    monkeypatch.setattr("services.play.gm.runtime.retrieve_gm_rules", lambda **kwargs: [])

    import services.play.gm.actions as actions_mod

    actions_mod._locks.clear()
    actions_mod._queues.clear()
    clear_memory_rate_limits()

    db = Session()
    host = User(clerk_id="host", email="host@ex.com")
    p2 = User(clerk_id="p2", email="p2@ex.com")
    stranger = User(clerk_id="stranger", email="s@ex.com")
    db.add_all([host, p2, stranger])
    db.commit()
    for u in (host, p2, stranger):
        db.refresh(u)

    job = Job(
        id="job-hard",
        user_id=host.id,
        status="completed",
        blueprint_json=json.dumps({"title": "Salt"}),
        book_id="bk_1",
        campaign_s3_key="c.md",
    )
    db.add(job)
    db.commit()
    campaign = Campaign(
        job_id=job.id,
        host_user_id=host.id,
        book_id="bk_1",
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

    payload = {
        "Session": Session,
        "host_id": host.id,
        "p2_id": p2.id,
        "stranger_id": stranger.id,
        "chars": [{"id": c.id, "display_name": c.display_name} for c in chars],
        "campaign_id": campaign.id,
        "session_id": gs.id,
    }
    db.close()
    yield payload


def test_non_member_cannot_submit_action(live_table):
    with pytest.raises(ActionError) as ei:
        submit_player_action(
            live_table["stranger_id"],
            live_table["session_id"],
            "I sneak in.",
            llm=MockGMLLM(),
            speak=False,
        )
    assert ei.value.code == "forbidden"


def test_tool_rejects_character_outside_session(live_table):
    Session = live_table["Session"]
    db = Session()
    from models.entities import GameSession

    gs = db.query(GameSession).filter_by(id=live_table["session_id"]).first()
    outsider = CampaignCharacter(
        campaign_id=live_table["campaign_id"],
        display_name="Ghost",
        sheet_json="{}",
        sort_order=9,
        claimable=True,
    )
    db.add(outsider)
    db.commit()
    db.refresh(outsider)

    ctx = ToolContext(
        db,
        gs,
        live_table["host_id"],
        live_table["chars"][0]["id"],
        dice_rng=lambda sides: 10,
    )
    out = execute_tool(
        ctx,
        "update_character",
        {"character_id": outsider.id, "fields": {"hp": 1}},
    )
    assert out["ok"] is False
    err = (out.get("error") or "").lower()
    assert "session" in err or "not" in err
    db.close()


def test_play_action_rate_limit(live_table, monkeypatch):
    monkeypatch.setenv("PLAY_ACTION_RATE_MAX", "2")
    monkeypatch.setenv("PLAY_ACTION_RATE_WINDOW", "60")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    clear_memory_rate_limits()
    submit_player_action(
        live_table["host_id"],
        live_table["session_id"],
        "One.",
        llm=MockGMLLM(),
        speak=False,
    )
    submit_player_action(
        live_table["host_id"],
        live_table["session_id"],
        "Two.",
        llm=MockGMLLM(),
        speak=False,
    )
    with pytest.raises(ActionError) as ei:
        submit_player_action(
            live_table["host_id"],
            live_table["session_id"],
            "Three.",
            llm=MockGMLLM(),
            speak=False,
        )
    assert ei.value.code == "rate_limited"


def test_gm_turn_logs_correlation_without_secrets(live_table, caplog):
    caplog.set_level(logging.INFO)
    result = submit_player_action(
        live_table["host_id"],
        live_table["session_id"],
        "I look around.",
        llm=MockGMLLM(),
        speak=False,
    )
    assert result["narration"]
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "gm_turn" in joined
    assert live_table["session_id"] in joined
    assert "request_id=" in joined
    assert "sk-" not in joined.lower()
    assert "character-private" not in joined.lower()


class HostileAgencyLLM:
    """Narrates another PC taking an unrequested voluntary action."""

    def complete_turn(self, context):
        return LLMTurn(
            tool_calls=[],
            narration="Without being asked, Joren draws his blade and charges the door.",
        )


def test_agency_rule_blocks_unrequested_other_pc_actions(live_table):
    result = submit_player_action(
        live_table["host_id"],
        live_table["session_id"],
        "I study the lock.",
        llm=HostileAgencyLLM(),
        speak=False,
    )
    text = (result["narration"] or "").lower()
    assert "joren draws" not in text
    assert "charges the door" not in text


def test_restart_recovers_active_session_state_and_events(live_table):
    submit_player_action(
        live_table["host_id"],
        live_table["session_id"],
        "I open the chest.",
        llm=MockGMLLM(),
        speak=False,
    )
    snap = get_reconnect_snapshot(
        live_table["p2_id"],
        live_table["session_id"],
        after_seq=0,
    )
    assert snap["session"]["status"] == "ACTIVE"
    assert snap["state"]
    assert snap["events"]
    assert snap["state_version"] >= 1
