"""Play Application boundary: create Campaign from a completed Job."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.entities import Campaign, CampaignCharacter, Job, User
from services.play.campaigns import (
    CampaignCreateError,
    create_campaign_from_job,
    get_campaign_for_user,
)


@pytest.fixture
def db_setup(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr("services.play.campaigns.SessionLocal", Session)
    monkeypatch.setattr("services.jobs_db.SessionLocal", Session)

    db = Session()
    user = User(clerk_id="host-1", email="host@example.com", plan="free", credits_balance=10)
    other = User(clerk_id="other-1", email="other@example.com", plan="free", credits_balance=10)
    db.add_all([user, other])
    db.commit()
    db.refresh(user)
    db.refresh(other)
    yield user, other, Session
    db.close()


def _completed_job(Session, user_id: str, **kwargs) -> Job:
    from services.jobs_db import create_job_record

    job = create_job_record(
        job_id=kwargs.get("job_id", "job-1"),
        user_id=user_id,
        complexity="simples",
        language="en",
        filename="book.pdf",
        credits_charged=0,
    )
    db = Session()
    row = db.query(Job).filter(Job.id == job.id).first()
    row.status = "completed"
    row.campaign_s3_key = "campaigns/demo.md"
    row.blueprint_json = json.dumps(
        kwargs.get(
            "blueprint",
            {"title": "Salt on the Throne", "sessions": [{"number": 1, "title": "Harbor"}]},
        )
    )
    row.book_id = kwargs.get("book_id", "bk_abc123")
    sheets = kwargs.get(
        "sheets",
        [
            {"name": "Mira", "class": "Fighter", "level": "3"},
            {"name": "Joren", "class": "Wizard", "level": "2"},
        ],
    )
    row.character_sheets = json.dumps(sheets) if sheets is not None else None
    db.commit()
    db.refresh(row)
    db.close()
    return row


def test_create_campaign_from_job_copies_blueprint_book_and_roster(db_setup):
    user, _other, Session = db_setup
    job = _completed_job(Session, user.id)

    campaign = create_campaign_from_job(user.id, job.id)

    assert campaign.id
    assert campaign.job_id == job.id
    assert campaign.host_user_id == user.id
    assert campaign.book_id == "bk_abc123"
    assert campaign.title == "Salt on the Throne"
    assert json.loads(campaign.blueprint_json)["title"] == "Salt on the Throne"
    assert campaign.manuscript_s3_key == "campaigns/demo.md"
    assert campaign.status == "ready"

    db = Session()
    chars = (
        db.query(CampaignCharacter)
        .filter(CampaignCharacter.campaign_id == campaign.id)
        .order_by(CampaignCharacter.sort_order)
        .all()
    )
    assert [c.display_name for c in chars][:2] == ["Mira", "Joren"]
    assert len(chars) >= 4  # pad to table seats even with fewer uploaded sheets
    assert all(c.claimable for c in chars)
    assert json.loads(chars[0].sheet_json)["class"] == "Fighter"
    db.close()


def test_create_campaign_rejects_non_owner(db_setup):
    user, other, Session = db_setup
    job = _completed_job(Session, user.id)
    with pytest.raises(CampaignCreateError) as exc:
        create_campaign_from_job(other.id, job.id)
    assert exc.value.code in {"forbidden", "not_found"}


def test_create_campaign_rejects_missing_blueprint(db_setup):
    user, _other, Session = db_setup
    job = _completed_job(Session, user.id)
    db = Session()
    row = db.query(Job).filter(Job.id == job.id).first()
    row.blueprint_json = None
    db.commit()
    db.close()

    with pytest.raises(CampaignCreateError) as exc:
        create_campaign_from_job(user.id, job.id)
    assert exc.value.code == "missing_blueprint"


def test_create_campaign_rejects_incomplete_job(db_setup):
    user, _other, Session = db_setup
    job = _completed_job(Session, user.id)
    db = Session()
    row = db.query(Job).filter(Job.id == job.id).first()
    row.status = "processing"
    db.commit()
    db.close()

    with pytest.raises(CampaignCreateError) as exc:
        create_campaign_from_job(user.id, job.id)
    assert exc.value.code == "job_not_ready"


def test_create_campaign_is_idempotent_for_same_job(db_setup):
    user, _other, Session = db_setup
    job = _completed_job(Session, user.id)
    first = create_campaign_from_job(user.id, job.id)
    second = create_campaign_from_job(user.id, job.id)
    assert first.id == second.id

    db = Session()
    assert db.query(Campaign).filter(Campaign.job_id == job.id).count() == 1
    db.close()


def test_get_campaign_for_user_requires_host(db_setup):
    user, other, Session = db_setup
    job = _completed_job(Session, user.id)
    campaign = create_campaign_from_job(user.id, job.id)
    assert get_campaign_for_user(user.id, campaign.id) is not None
    assert get_campaign_for_user(other.id, campaign.id) is None
