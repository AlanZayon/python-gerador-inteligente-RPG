"""Play Application: reconnect snapshot + event fan-out (WS gateway boundary)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models.entities import Campaign, CampaignCharacter, Job, User
from services.play.gm import MockGMLLM, submit_player_action
from services.play.hub import SessionHub
from services.play.sessions import (
    claim_character,
    create_game_session,
    join_game_session,
    set_ready,
    start_game_session,
)
from services.play.sync import SyncError, get_reconnect_snapshot, set_presence


@pytest.fixture
def live_table(monkeypatch):
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
        "services.play.sync.SessionLocal",
    ):
        monkeypatch.setattr(path, Session)

    hub = SessionHub()
    monkeypatch.setattr("services.play.hub.default_hub", hub)

    db = Session()
    host = User(clerk_id="host", email="host@ex.com")
    p2 = User(clerk_id="p2", email="p2@ex.com")
    db.add_all([host, p2])
    db.commit()
    for u in (host, p2):
        db.refresh(u)

    job = Job(
        id="job-ws",
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
        "hub": hub,
        "host": host,
        "p2": p2,
        "chars": chars,
        "session_id": gs.id,
    }
    db.close()
    yield payload


def test_member_gets_reconnect_snapshot_with_state_and_events(live_table):
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I look around.",
        llm=MockGMLLM(),
    )
    snap = get_reconnect_snapshot(live_table["p2"].id, live_table["session_id"], after_seq=0)
    assert snap["session"]["id"] == live_table["session_id"]
    assert "state" in snap
    assert snap["events"]
    assert snap["last_seq"] >= 1
    assert any(e["type"] == "gm_narration" for e in snap["events"])


def test_reconnect_returns_only_missed_events(live_table):
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "First action.",
        llm=MockGMLLM(),
    )
    first = get_reconnect_snapshot(live_table["host"].id, live_table["session_id"], after_seq=0)
    cursor = first["last_seq"]
    submit_player_action(
        live_table["p2"].id,
        live_table["session_id"],
        "Second action.",
        llm=MockGMLLM(),
    )
    missed = get_reconnect_snapshot(
        live_table["host"].id, live_table["session_id"], after_seq=cursor
    )
    assert missed["events"]
    assert all(e["seq"] > cursor for e in missed["events"])
    assert any("Second" in json.dumps(e.get("payload") or {}) for e in missed["events"])


def test_non_member_cannot_snapshot(live_table):
    stranger = User(clerk_id="stranger", email="s@ex.com")
    db = live_table["Session"]()
    db.add(stranger)
    db.commit()
    db.refresh(stranger)
    db.close()
    with pytest.raises(SyncError) as exc:
        get_reconnect_snapshot(stranger.id, live_table["session_id"], after_seq=0)
    assert exc.value.code in {"forbidden", "not_found"}


def test_two_connection_lifecycles_receive_broadcast_and_resync(live_table):
    hub: SessionHub = live_table["hub"]
    inbox_a: list[dict] = []
    inbox_b: list[dict] = []

    hub.subscribe(live_table["session_id"], "conn-a", live_table["host"].id, inbox_a.append)
    set_presence(live_table["host"].id, live_table["session_id"], connected=True)
    hub.subscribe(live_table["session_id"], "conn-b", live_table["p2"].id, inbox_b.append)
    set_presence(live_table["p2"].id, live_table["session_id"], connected=True)

    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "GM_SCRIPT:hidden_roll 1d20",
        llm=MockGMLLM(),
        dice_rng=lambda sides: 11,
    )

    assert any(m.get("type") == "gm_narration" for m in inbox_a)
    assert any(m.get("type") == "dice_result" or m.get("type") == "gm_narration" for m in inbox_b)

    # A disconnects; B stays. A reconnects via DB snapshot (not process memory).
    hub.unsubscribe(live_table["session_id"], "conn-a")
    set_presence(live_table["host"].id, live_table["session_id"], connected=False)
    last_seen = max((m.get("seq") or 0 for m in inbox_a), default=0)

    submit_player_action(
        live_table["p2"].id,
        live_table["session_id"],
        "While A is gone.",
        llm=MockGMLLM(),
    )
    assert any(
        m.get("type") == "gm_narration" and "While A is gone" in json.dumps(m.get("payload") or {})
        for m in inbox_b
    )

    resync = get_reconnect_snapshot(
        live_table["host"].id, live_table["session_id"], after_seq=last_seen
    )
    assert any(
        "While A is gone" in json.dumps(e.get("payload") or {}) for e in resync["events"]
    )
    presence = {p["user_id"]: p["connected"] for p in resync["presence"]}
    assert presence[live_table["host"].id] is False
    assert presence[live_table["p2"].id] is True


def test_http_text_action_still_works_without_subscribers(live_table):
    # No hub subscribers — table must not soft-lock.
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "Quiet table.",
        llm=MockGMLLM(),
    )
    assert result["narration"]
    snap = get_reconnect_snapshot(live_table["host"].id, live_table["session_id"], after_seq=0)
    assert snap["events"]
