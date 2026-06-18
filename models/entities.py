"""SQLAlchemy models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    clerk_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    plan: Mapped[str] = mapped_column(String(32), default="free")
    credits_balance: Mapped[int] = mapped_column(Integer, default=1)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    api_key_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    jobs: Mapped[list["Job"]] = relationship(back_populates="user")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    complexity: Mapped[str] = mapped_column(String(32), default="mediana")
    language: Mapped[str] = mapped_column(String(8), default="en")
    filename: Mapped[str] = mapped_column(String(512), default="")
    s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    campaign_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    credits_charged: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    share_slug: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    share_public: Mapped[bool] = mapped_column(Boolean, default=False)
    system_preset: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="jobs")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    plan: Mapped[str] = mapped_column(String(32), default="free")
    status: Mapped[str] = mapped_column(String(32), default="active")
    period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="subscriptions")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(64))
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), default="")
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
