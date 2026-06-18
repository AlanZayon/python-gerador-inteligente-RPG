"""Quota deduction and refund tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.entities import CreditTransaction, User
from services.quota import QuotaError, check_and_deduct, refund_credits


@pytest.fixture
def db_setup(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr("services.quota.SessionLocal", Session)

    db = Session()
    user = User(clerk_id="test-clerk", email="test@example.com", plan="free", credits_balance=1)
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user, Session
    db.close()


def test_check_and_deduct_simple(db_setup):
    user, Session = db_setup
    cost = check_and_deduct(user, "simples", "job-1")
    assert cost == 1

    db = Session()
    updated = db.query(User).filter(User.id == user.id).first()
    assert updated.credits_balance == 0
    tx = db.query(CreditTransaction).filter(CreditTransaction.job_id == "job-1").first()
    assert tx.amount == -1
    db.close()


def test_plan_restriction_raises_402_payload(db_setup):
    user, _Session = db_setup
    with pytest.raises(QuotaError) as exc:
        check_and_deduct(user, "mediana", "job-2")
    assert exc.value.payload["error"] == "plan_restriction"


def test_refund_credits(db_setup):
    user, Session = db_setup
    check_and_deduct(user, "simples", "job-3")
    refund_credits(user.id, 1, "job-3")

    db = Session()
    updated = db.query(User).filter(User.id == user.id).first()
    assert updated.credits_balance == 1
    db.close()
