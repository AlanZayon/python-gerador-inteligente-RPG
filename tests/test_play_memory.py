"""Play Application: session / campaign / character-private memory."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models.entities import Campaign, CampaignCharacter, Job, Memory, User
from services.play.gm import MockGMLLM, submit_player_action
from services.play.gm.mock_llm import LLMTurn
from services.play.memory import (
    filter_memories_for_character,
    filter_public_narration,
    list_memories_for_gm,
    write_memory,
)
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
    for path in (
        "services.play.sessions.SessionLocal",
        "services.play.gm.runtime.SessionLocal",
        "services.play.gm.actions.SessionLocal",
        "services.play.memory.SessionLocal",
    ):
        monkeypatch.setattr(path, Session)
    monkeypatch.setattr("services.play.gm.runtime.retrieve_gm_rules", lambda **kwargs: [])

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
        id="job-mem",
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
        "host": host,
        "p2": p2,
        "chars": chars,
        "campaign": campaign,
        "session_id": gs.id,
    }
    db.close()
    yield payload


class MemoryScriptLLM(MockGMLLM):
    """Scripted GM that writes memories on cue, then uses them on later turns."""

    def complete_turn(self, context):
        action = (context.get("player_action") or "").strip()
        lower = action.lower()
        character_id = context.get("actor_character_id")

        if "secret passphrase" in lower or "whisper" in lower:
            return LLMTurn(
                tool_calls=[
                    {
                        "name": "write_memory",
                        "args": {
                            "scope": "character_private",
                            "character_id": character_id,
                            "content": "The vault passphrase is SILVER-GULL.",
                        },
                    },
                    {
                        "name": "write_memory",
                        "args": {
                            "scope": "session",
                            "content": "Party investigated the harbormaster's ledger.",
                        },
                    },
                    {
                        "name": "write_memory",
                        "args": {
                            "scope": "campaign",
                            "content": "The Salt conspiracy touches the dock guild.",
                        },
                    },
                ],
                narration="You alone overhear a whispered passphrase.",
            )

        if "what do i remember" in lower:
            mems = context.get("memories_gm") or []
            private = [m for m in mems if m.get("scope") == "character_private"]
            text = private[0]["content"] if private else "nothing private"
            # Deliberately leak into narration — filter must scrub for public broadcast.
            return LLMTurn(
                tool_calls=[],
                narration=f"Publicly you recall: {text}",
            )

        return super().complete_turn(context)


def test_session_and_campaign_memories_persist_across_turns(live_table):
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I whisper to learn the secret passphrase.",
        llm=MemoryScriptLLM(),
    )
    gm_memories = list_memories_for_gm(
        campaign_id=live_table["campaign"].id,
        game_session_id=live_table["session_id"],
    )
    scopes = {m["scope"] for m in gm_memories}
    assert "session" in scopes
    assert "campaign" in scopes
    assert "character_private" in scopes

    # Second turn: GM context includes prior memories
    captured = {}

    class Capture(MemoryScriptLLM):
        def complete_turn(self, context):
            captured["memories_gm"] = context.get("memories_gm")
            return LLMTurn(tool_calls=[], narration="Noted.")

    submit_player_action(
        live_table["p2"].id,
        live_table["session_id"],
        "I look around.",
        llm=Capture(),
    )
    assert any(m["scope"] == "session" for m in captured["memories_gm"])
    assert any(m["scope"] == "campaign" for m in captured["memories_gm"])


def test_character_private_not_in_other_player_filtered_context(live_table):
    mira_id = live_table["chars"][0].id
    joren_id = live_table["chars"][1].id
    write_memory(
        campaign_id=live_table["campaign"].id,
        game_session_id=live_table["session_id"],
        scope="character_private",
        content="The vault passphrase is SILVER-GULL.",
        character_id=mira_id,
    )
    write_memory(
        campaign_id=live_table["campaign"].id,
        game_session_id=live_table["session_id"],
        scope="session",
        content="We found a torn map.",
    )

    for_mira = filter_memories_for_character(
        campaign_id=live_table["campaign"].id,
        game_session_id=live_table["session_id"],
        character_id=mira_id,
    )
    for_joren = filter_memories_for_character(
        campaign_id=live_table["campaign"].id,
        game_session_id=live_table["session_id"],
        character_id=joren_id,
    )
    mira_texts = " ".join(m["content"] for m in for_mira)
    joren_texts = " ".join(m["content"] for m in for_joren)
    assert "SILVER-GULL" in mira_texts
    assert "SILVER-GULL" not in joren_texts
    assert "torn map" in joren_texts


def test_public_narration_does_not_leak_private_secrets(live_table):
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I whisper to learn the secret passphrase.",
        llm=MemoryScriptLLM(),
    )
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "What do I remember?",
        llm=MemoryScriptLLM(),
    )
    assert "SILVER-GULL" not in result["narration"]
    # GM still knows privately
    gm = list_memories_for_gm(
        campaign_id=live_table["campaign"].id,
        game_session_id=live_table["session_id"],
    )
    assert any("SILVER-GULL" in m["content"] for m in gm)

    # Second Player turn: filtered context must not include Mira's secret
    captured = {}

    class SecondPlayerCapture(MockGMLLM):
        def complete_turn(self, context):
            captured["memories_player"] = context.get("memories_player")
            captured["memories_gm"] = context.get("memories_gm")
            return LLMTurn(tool_calls=[], narration="Joren notices nothing unusual.")

    other = submit_player_action(
        live_table["p2"].id,
        live_table["session_id"],
        "I watch Mira carefully.",
        llm=SecondPlayerCapture(),
    )
    player_texts = " ".join(m["content"] for m in captured["memories_player"])
    assert "SILVER-GULL" not in player_texts
    assert "SILVER-GULL" not in other["narration"]
    assert any("SILVER-GULL" in m["content"] for m in captured["memories_gm"])


def test_filter_public_narration_helper():
    private = [{"content": "The vault passphrase is SILVER-GULL."}]
    scrubbed = filter_public_narration(
        "Publicly you recall: The vault passphrase is SILVER-GULL.",
        private,
    )
    assert "SILVER-GULL" not in scrubbed
