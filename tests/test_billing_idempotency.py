"""Stripe webhook idempotency tests."""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database import Base
from models.entities import StripeEvent
from routes.billing import _record_stripe_event


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def test_stripe_event_unique_constraint(session_factory):
    db = session_factory()
    db.add(StripeEvent(event_id="evt_1", event_type="checkout.session.completed", session_id="cs_1"))
    db.commit()
    db.add(StripeEvent(event_id="evt_1", event_type="checkout.session.completed", session_id="cs_1"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.close()


def test_record_stripe_event_rejects_duplicate(session_factory):
    event = {
        "id": "evt_test_123",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_1"}},
    }

    with patch("routes.billing.SessionLocal", session_factory):
        assert _record_stripe_event(event) is True
        assert _record_stripe_event(event) is False

        db = session_factory()
        assert db.query(StripeEvent).filter(StripeEvent.event_id == "evt_test_123").count() == 1
        db.close()
