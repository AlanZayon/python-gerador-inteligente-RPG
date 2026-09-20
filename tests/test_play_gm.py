"""Play Application: text GM turn with mock LLM."""

from __future__ import annotations

import json
import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models.entities import Campaign, CampaignCharacter, GameEvent, GameSession, Job, SessionPlayer, User
from services.play.gm import MockGMLLM, submit_player_action
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
        id="job-gm",
        user_id=host.id,
        status="completed",
        blueprint_json=json.dumps({"title": "Salt", "premise": "Storms gather."}),
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
            sheet_json=json.dumps({"name": name, "hp": 10}),
            sort_order=i,
            claimable=True,
        )
        db.add(c)
        chars.append(c)
    db.commit()
    for c in chars:
        db.refresh(c)
    db.refresh(campaign)

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
        "campaign": campaign,
        "chars": chars,
        "session_id": gs.id,
    }
    # Release the fixture connection before tests; StaticPool shares one SQLite
    # connection and a held Session races with concurrent GM flights.
    db.close()
    yield payload


def test_member_with_character_can_submit_text_action(live_table):
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I look around the docks.",
        llm=MockGMLLM(),
    )
    assert result["narration"]
    assert result["state"]["scene"] or result["state"].get("notes") is not None
    assert result["events"]


def test_non_member_cannot_submit(live_table):
    stranger = User(clerk_id="x", email="x@ex.com")
    db = live_table["Session"]()
    db.add(stranger)
    db.commit()
    db.refresh(stranger)
    db.close()
    with pytest.raises(Exception) as exc:
        submit_player_action(stranger.id, live_table["session_id"], "hi", llm=MockGMLLM())
    assert getattr(exc.value, "code", None) in {"forbidden", "not_found"}


def test_dice_tool_is_authoritative_not_invented(live_table):
    rolls = iter([17])

    def rng(sides: int) -> int:
        assert sides == 20
        return next(rolls)

    result = submit_player_action(
        live_table["p2"].id,
        live_table["session_id"],
        "GM_SCRIPT:hidden_roll 1d20",
        llm=MockGMLLM(),
        dice_rng=rng,
    )
    assert result["state"]["last_dice"]["total"] == 17
    assert "17" in result["narration"]
    # Mock must not invent a different total in narration-only path
    assert result["tool_results"]
    assert any(t["name"] == "roll_dice" for t in result["tool_results"])


def test_two_rapid_actions_serialize_without_corrupting_state(live_table):
    results = []
    errors = []

    def act(user_id, text):
        try:
            results.append(
                submit_player_action(
                    user_id,
                    live_table["session_id"],
                    text,
                    llm=MockGMLLM(),
                )
            )
        except Exception as exc:  # noqa: BLE001
            import traceback

            errors.append(f"{exc!r}\n{traceback.format_exc()}")

    t1 = threading.Thread(target=act, args=(live_table["host"].id, "I open the chest."))
    t2 = threading.Thread(target=act, args=(live_table["p2"].id, "I watch the door."))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert not errors
    assert len(results) == 2

    db = live_table["Session"]()
    gs = db.query(GameSession).filter(GameSession.id == live_table["session_id"]).first()
    state = json.loads(gs.state_json)
    assert gs.state_version == 2
    events = (
        db.query(GameEvent)
        .filter(GameEvent.game_session_id == live_table["session_id"])
        .order_by(GameEvent.seq)
        .all()
    )
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)
    assert state["notes"] or state.get("scene") is not None
    db.close()


def test_update_world_and_character_tools_persist(live_table):
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "GM_SCRIPT: move to Harbor and set Mira hp to 7",
        llm=MockGMLLM(),
    )
    assert result["state"]["location"] == "Harbor"
    char_id = live_table["chars"][0].id
    assert result["state"]["characters"][char_id]["hp"] == 7


def test_perform_check_and_npc_clock_surface(live_table):
    result2 = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "GM_SCRIPT: move to Wharf",
        llm=MockGMLLM(),
    )
    # exercise npc_flags/clocks via direct tool path through a second scripted update
    from services.play.gm.tools import ToolContext, execute_tool
    from models.entities import GameSession

    db = live_table["Session"]()
    gs = db.query(GameSession).filter(GameSession.id == live_table["session_id"]).first()
    ctx = ToolContext(db, gs, live_table["host"].id, live_table["chars"][0].id)
    execute_tool(
        ctx,
        "update_world_state",
        {"patch": {"npc_flags": {"dockmaster": "wary"}, "clocks": {"storm": 2}}},
    )
    execute_tool(ctx, "update_quest", {"quest_id": "main", "fields": {"progress": 1}})
    ctx.persist_state(bump_version=True)
    db.commit()
    state = json.loads(gs.state_json)
    assert state["npc_flags"]["dockmaster"] == "wary"
    assert state["clocks"]["storm"] == 2
    assert state["quests"]["main"]["progress"] == 1
    assert result2["state"]["location"] == "Wharf"
    db.close()
