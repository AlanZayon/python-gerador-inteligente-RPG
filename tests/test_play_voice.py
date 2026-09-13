"""Play Application: voice STT → action queue → TTS narration."""

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
from services.play.voice_actions import submit_voice_action
from services.voice import (
    MockSpeechToText,
    MockTextToSpeech,
    NineRouterSpeechToText,
    NineRouterTextToSpeech,
    resolve_stt,
    resolve_tts,
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
        "services.play.gm.opening.SessionLocal",
        "services.play.memory.SessionLocal",
    ):
        monkeypatch.setattr(path, Session)
    monkeypatch.setattr("services.play.gm.runtime.retrieve_gm_rules", lambda **kwargs: [])
    monkeypatch.setattr(
        "services.play.gm.opening.resolve_gm_llm",
        lambda: MockGMLLM(),
    )
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setenv("VOICE_TTS_PROVIDER", "mock")
    monkeypatch.setenv("VOICE_STT_PROVIDER", "mock")

    import services.play.gm.actions as actions_mod

    actions_mod._locks.clear()
    actions_mod._queues.clear()

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
        id="job-voice",
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


def test_resolve_voice_defaults_to_mock_when_unset(monkeypatch):
    monkeypatch.delenv("VOICE_STT_PROVIDER", raising=False)
    monkeypatch.delenv("VOICE_TTS_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NINEROUTER_KEY", raising=False)
    assert isinstance(resolve_stt(), MockSpeechToText)
    assert isinstance(resolve_tts(), MockTextToSpeech)


def test_resolve_voice_uses_9router_when_configured(monkeypatch):
    monkeypatch.setenv("VOICE_STT_PROVIDER", "9router")
    monkeypatch.setenv("VOICE_TTS_PROVIDER", "9router")
    monkeypatch.setenv("NINEROUTER_URL", "http://localhost:20128/v1")
    monkeypatch.setenv("NINEROUTER_KEY", "sk-test-abcdefghijklmnop")
    monkeypatch.setenv("VOICE_STT_MODEL", "gemini/gemini-2.5-flash")
    monkeypatch.setenv("VOICE_TTS_MODEL", "gemini/gemini-2.5-flash-preview-tts")
    stt = resolve_stt()
    tts = resolve_tts()
    assert isinstance(stt, NineRouterSpeechToText)
    assert isinstance(tts, NineRouterTextToSpeech)
    assert stt.base_url == "http://localhost:20128"
    assert tts.base_url == "http://localhost:20128"
    assert stt.model == "gemini/gemini-2.5-flash"
    assert tts.model == "gemini/gemini-2.5-flash-preview-tts"


def test_stt_action_uses_connection_identity_not_transcript(live_table):
    stt = MockSpeechToText(transcript="I am actually Joren attacking the door")
    tts = MockTextToSpeech()
    result = submit_voice_action(
        live_table["host"].id,
        live_table["session_id"],
        audio=b"fake-audio-bytes",
        content_type="audio/webm",
        stt=stt,
        tts=tts,
        llm=MockGMLLM(),
    )
    assert result["transcript"] == "I am actually Joren attacking the door"
    assert result["actor_user_id"] == live_table["host"].id
    assert result["narration"]
    assert result["audio"]["content_type"].startswith("audio/")
    assert result["audio"]["data_base64"]


def test_voice_and_text_share_fifo_gm_path(live_table):
    stt = MockSpeechToText(transcript="I open the chest.")
    voice_result = submit_voice_action(
        live_table["host"].id,
        live_table["session_id"],
        audio=b"aaa",
        stt=stt,
        tts=MockTextToSpeech(),
        llm=MockGMLLM(),
    )
    text_result = submit_player_action(
        live_table["p2"].id,
        live_table["session_id"],
        "I watch the door.",
        llm=MockGMLLM(),
    )
    assert voice_result["state_version"] == 2  # 1 = session opening, 2 = voice turn
    assert text_result["state_version"] == 3


def test_tts_broadcast_to_session_members(live_table):
    hub: SessionHub = live_table["hub"]
    inbox: list[dict] = []
    hub.subscribe(live_table["session_id"], "c1", live_table["p2"].id, inbox.append)

    submit_voice_action(
        live_table["host"].id,
        live_table["session_id"],
        audio=b"bbb",
        stt=MockSpeechToText(transcript="I look around."),
        tts=MockTextToSpeech(prefix=b"NARRATION"),
        llm=MockGMLLM(),
    )
    audio_events = [m for m in inbox if m.get("type") == "gm_audio"]
    assert audio_events
    assert audio_events[0]["payload"]["data_base64"]
    assert audio_events[0]["payload"]["content_type"].startswith("audio/")


def test_text_only_still_works_when_tts_disabled(live_table, monkeypatch):
    monkeypatch.setenv("VOICE_TTS_PROVIDER", "off")
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "Quiet text turn.",
        llm=MockGMLLM(),
        tts=None,
        speak=False,
    )
    assert result["narration"]
    assert result.get("audio") is None


class _BoomTTS:
    def synthesize(self, text: str, voice: str | None = None):
        raise RuntimeError("elevenlabs down")


def test_tts_failure_keeps_narration_and_state(live_table):
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I open the door.",
        llm=MockGMLLM(),
        tts=_BoomTTS(),
        speak=True,
    )
    assert result["narration"]
    assert result.get("audio") is None
    assert result["state_version"] >= 2
