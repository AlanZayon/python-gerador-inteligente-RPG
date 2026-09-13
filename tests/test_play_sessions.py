"""Play Application boundary: GameSession lobby lifecycle."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.entities import Campaign, CampaignCharacter, GameSession, Job, SessionPlayer, User
from services.play.sessions import (
    SessionError,
    claim_character,
    create_game_session,
    end_game_session,
    get_session_for_user,
    join_game_session,
    set_ready,
    start_game_session,
)


@pytest.fixture
def db_setup(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr("services.play.sessions.SessionLocal", Session)
    monkeypatch.setattr("services.play.campaigns.SessionLocal", Session)
    monkeypatch.setattr("services.play.gm.opening.SessionLocal", Session)
    monkeypatch.setattr(
        "services.play.gm.opening.resolve_gm_llm",
        lambda: __import__("services.play.gm.mock_llm", fromlist=["MockGMLLM"]).MockGMLLM(),
    )

    db = Session()
    host = User(clerk_id="host", email="host@ex.com")
    p2 = User(clerk_id="p2", email="p2@ex.com")
    p3 = User(clerk_id="p3", email="p3@ex.com")
    p4 = User(clerk_id="p4", email="p4@ex.com")
    p5 = User(clerk_id="p5", email="p5@ex.com")
    db.add_all([host, p2, p3, p4, p5])
    db.commit()
    for u in (host, p2, p3, p4, p5):
        db.refresh(u)

    job = Job(
        id="job-lobby",
        user_id=host.id,
        status="completed",
        blueprint_json=json.dumps(
            {
                "title": "Salt on the Throne",
                "premise": "Storms gather over the salt flats and old debts come due.",
                "central_conflict": "Smugglers versus the crown's tax collectors.",
                "stakes": "Whoever controls the flats controls the winter grain.",
                "tone": "gritty",
                "sessions": [
                    {
                        "number": 1,
                        "title": "Broken Seal",
                        "dramatic_function": "hook",
                        "scenes": [
                            {
                                "name": "The Dockyard",
                                "location": "South pier",
                                "purpose": "Discover the broken seal and choose who to trust",
                            }
                        ],
                    }
                ],
            }
        ),
        book_id="bk_1",
        campaign_s3_key="c.md",
    )
    db.add(job)
    db.commit()

    campaign = Campaign(
        job_id=job.id,
        host_user_id=host.id,
        book_id="bk_1",
        title="Salt on the Throne",
        blueprint_json=job.blueprint_json,
        status="ready",
    )
    db.add(campaign)
    db.flush()
    for i, name in enumerate(["Mira", "Joren", "Ash", "Vex"]):
        db.add(
            CampaignCharacter(
                campaign_id=campaign.id,
                display_name=name,
                sheet_json=json.dumps({"name": name}),
                sort_order=i,
                claimable=True,
            )
        )
    db.commit()
    db.refresh(campaign)
    yield {
        "Session": Session,
        "host": host,
        "players": [p2, p3, p4, p5],
        "campaign": campaign,
    }
    db.close()


def _chars(Session, campaign_id):
    return (
        Session()
        .query(CampaignCharacter)
        .filter(CampaignCharacter.campaign_id == campaign_id)
        .order_by(CampaignCharacter.sort_order)
        .all()
    )


def test_host_creates_lobby_with_invite(db_setup):
    host = db_setup["host"]
    campaign = db_setup["campaign"]
    gs = create_game_session(host.id, campaign.id)
    assert gs.status == "LOBBY"
    assert gs.invite_code
    assert len(gs.invite_code) >= 6
    assert gs.campaign_id == campaign.id


def test_create_returns_existing_active_session(db_setup):
    host = db_setup["host"]
    campaign = db_setup["campaign"]
    first = create_game_session(host.id, campaign.id)
    second = create_game_session(host.id, campaign.id)
    assert second.id == first.id
    assert second.invite_code == first.invite_code


def test_players_join_via_invite(db_setup):
    host = db_setup["host"]
    p2, p3 = db_setup["players"][:2]
    campaign = db_setup["campaign"]
    gs = create_game_session(host.id, campaign.id)
    sp2 = join_game_session(p2.id, gs.invite_code)
    sp3 = join_game_session(p3.id, gs.invite_code)
    assert sp2.game_session_id == gs.id
    assert sp3.user_id == p3.id


def test_join_rejects_capacity_over_four(db_setup):
    host = db_setup["host"]
    players = db_setup["players"]
    campaign = db_setup["campaign"]
    gs = create_game_session(host.id, campaign.id)
    for p in players[:3]:
        join_game_session(p.id, gs.invite_code)
    # host + 3 = 4; fifth should fail
    with pytest.raises(SessionError) as exc:
        join_game_session(players[3].id, gs.invite_code)
    assert exc.value.code == "full"


def test_claim_character_unique(db_setup):
    host = db_setup["host"]
    p2 = db_setup["players"][0]
    campaign = db_setup["campaign"]
    Session = db_setup["Session"]
    gs = create_game_session(host.id, campaign.id)
    join_game_session(p2.id, gs.invite_code)
    chars = _chars(Session, campaign.id)
    claim_character(host.id, gs.id, chars[0].id)
    with pytest.raises(SessionError) as exc:
        claim_character(p2.id, gs.id, chars[0].id)
    assert exc.value.code == "character_taken"
    claim_character(p2.id, gs.id, chars[1].id)


def test_start_requires_two_to_four_claimed_players(db_setup):
    host = db_setup["host"]
    p2 = db_setup["players"][0]
    campaign = db_setup["campaign"]
    Session = db_setup["Session"]
    gs = create_game_session(host.id, campaign.id)
    chars = _chars(Session, campaign.id)

    with pytest.raises(SessionError) as exc:
        start_game_session(host.id, gs.id)
    assert exc.value.code == "not_ready"

    join_game_session(p2.id, gs.invite_code)
    claim_character(host.id, gs.id, chars[0].id)
    claim_character(p2.id, gs.id, chars[1].id)
    set_ready(host.id, gs.id, True)
    set_ready(p2.id, gs.id, True)

    started = start_game_session(host.id, gs.id)
    assert started.status == "ACTIVE"
    db = Session()
    from models.entities import GameEvent

    narr = (
        db.query(GameEvent)
        .filter(GameEvent.game_session_id == gs.id, GameEvent.type == "gm_narration")
        .order_by(GameEvent.seq.desc())
        .first()
    )
    assert narr is not None
    payload = json.loads(narr.payload_json)
    assert payload.get("kind") == "session_opening"
    text = payload.get("text") or ""
    assert text
    assert "Storms gather" in text
    assert "Dockyard" in text or "broken seal" in text.lower()
    db.close()


def test_non_host_cannot_start_or_end(db_setup):
    host = db_setup["host"]
    p2 = db_setup["players"][0]
    campaign = db_setup["campaign"]
    Session = db_setup["Session"]
    gs = create_game_session(host.id, campaign.id)
    join_game_session(p2.id, gs.invite_code)
    chars = _chars(Session, campaign.id)
    claim_character(host.id, gs.id, chars[0].id)
    claim_character(p2.id, gs.id, chars[1].id)
    set_ready(host.id, gs.id, True)
    set_ready(p2.id, gs.id, True)

    with pytest.raises(SessionError) as exc:
        start_game_session(p2.id, gs.id)
    assert exc.value.code == "forbidden"

    start_game_session(host.id, gs.id)
    with pytest.raises(SessionError):
        end_game_session(p2.id, gs.id)
    ended = end_game_session(host.id, gs.id)
    assert ended.status == "ENDED"


def test_after_end_can_create_new_session(db_setup):
    host = db_setup["host"]
    campaign = db_setup["campaign"]
    gs = create_game_session(host.id, campaign.id)
    end_game_session(host.id, gs.id)
    gs2 = create_game_session(host.id, campaign.id)
    assert gs2.id != gs.id
    assert gs2.status == "LOBBY"


def test_get_session_for_member(db_setup):
    host = db_setup["host"]
    p2 = db_setup["players"][0]
    campaign = db_setup["campaign"]
    gs = create_game_session(host.id, campaign.id)
    join_game_session(p2.id, gs.invite_code)
    assert get_session_for_user(host.id, gs.id) is not None
    assert get_session_for_user(p2.id, gs.id) is not None
    outsider = db_setup["players"][3]
    assert get_session_for_user(outsider.id, gs.id) is None
