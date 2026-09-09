"""Persist Campaign Blueprint seed on Job records."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.entities import Job, User
from services.jobs_db import create_job_record, update_job_blueprint_seed, update_job_status


@pytest.fixture
def db_setup(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr("services.jobs_db.SessionLocal", Session)

    db = Session()
    user = User(clerk_id="c1", email="a@b.com", plan="free", credits_balance=10)
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user, Session
    db.close()


def test_update_job_blueprint_seed_persists_json(db_setup):
    user, Session = db_setup
    job = create_job_record(
        job_id="job-bp-1",
        user_id=user.id,
        complexity="simples",
        language="en",
        filename="book.pdf",
        credits_charged=0,
    )
    seed = {"title": "Salt on the Throne", "sessions": [{"number": 1, "title": "Harbor"}]}
    update_job_blueprint_seed(job.id, seed)

    db = Session()
    stored = db.query(Job).filter(Job.id == job.id).first()
    assert stored.blueprint_json is not None
    assert json.loads(stored.blueprint_json)["title"] == "Salt on the Throne"
    db.close()


def test_update_job_blueprint_seed_none_clears_or_skips(db_setup):
    user, Session = db_setup
    job = create_job_record(
        job_id="job-bp-2",
        user_id=user.id,
        complexity="simples",
        language="en",
        filename="book.pdf",
        credits_charged=0,
    )
    update_job_blueprint_seed(job.id, None)
    db = Session()
    stored = db.query(Job).filter(Job.id == job.id).first()
    assert stored.blueprint_json is None
    db.close()


def test_completed_status_can_include_blueprint(db_setup):
    user, Session = db_setup
    job = create_job_record(
        job_id="job-bp-3",
        user_id=user.id,
        complexity="mediana",
        language="en",
        filename="book.pdf",
        credits_charged=0,
    )
    seed = {"title": "Echoes", "npcs": []}
    update_job_status(
        job.id,
        "completed",
        campaign_s3_key="campaigns/x.md",
        blueprint_seed=seed,
    )
    db = Session()
    stored = db.query(Job).filter(Job.id == job.id).first()
    assert stored.status == "completed"
    assert json.loads(stored.blueprint_json)["title"] == "Echoes"
    db.close()
