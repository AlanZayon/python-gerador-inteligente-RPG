"""SQLAlchemy models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text as sa_text
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
    use_character_sheets: Mapped[bool] = mapped_column(Boolean, default=False)
    party_size: Mapped[int] = mapped_column(Integer, default=0)
    character_sheets: Mapped[str | None] = mapped_column(Text, nullable=True)
    blueprint_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    book_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="jobs")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), unique=True, index=True)
    host_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    book_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    blueprint_json: Mapped[str] = mapped_column(Text, default="{}")
    manuscript_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    characters: Mapped[list["CampaignCharacter"]] = relationship(
        back_populates="campaign",
        order_by="CampaignCharacter.sort_order",
    )


class CampaignCharacter(Base):
    __tablename__ = "campaign_characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(String(36), ForeignKey("campaigns.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    sheet_json: Mapped[str] = mapped_column(Text, default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    claimable: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    campaign: Mapped["Campaign"] = relationship(back_populates="characters")


class GameSession(Base):
    __tablename__ = "game_sessions"
    __table_args__ = (
        Index(
            "uq_game_sessions_active_campaign",
            "campaign_id",
            unique=True,
            sqlite_where=sa_text("status IN ('LOBBY', 'STARTING', 'ACTIVE', 'PAUSED')"),
            postgresql_where=sa_text("status IN ('LOBBY', 'STARTING', 'ACTIVE', 'PAUSED')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(String(36), ForeignKey("campaigns.id"), index=True)
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="LOBBY")
    host_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    state_json: Mapped[str] = mapped_column(Text, default="{}")
    state_version: Mapped[int] = mapped_column(Integer, default=0)
    current_scene: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    players: Mapped[list["SessionPlayer"]] = relationship(back_populates="game_session")


class SessionPlayer(Base):
    __tablename__ = "session_players"
    __table_args__ = (
        Index(
            "uq_session_player_user",
            "game_session_id",
            "user_id",
            unique=True,
        ),
        Index(
            "uq_session_player_character",
            "game_session_id",
            "character_id",
            unique=True,
            sqlite_where=sa_text("character_id IS NOT NULL"),
            postgresql_where=sa_text("character_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    game_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("game_sessions.id"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    character_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("campaign_characters.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(32), default="player")
    ready: Mapped[bool] = mapped_column(Boolean, default=False)
    connected: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    game_session: Mapped["GameSession"] = relationship(back_populates="players")


class GameEvent(Base):
    __tablename__ = "game_events"
    __table_args__ = (
        Index("uq_game_event_seq", "game_session_id", "seq", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    game_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("game_sessions.id"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(String(36), ForeignKey("campaigns.id"), index=True)
    game_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("game_sessions.id"), nullable=True, index=True
    )
    scope: Mapped[str] = mapped_column(String(32))  # session | campaign | character_private
    character_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("campaign_characters.id"), nullable=True, index=True
    )
    content_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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


class BookIndex(Base):
    __tablename__ = "book_indexes"

    book_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    fingerprints_json: Mapped[str] = mapped_column(Text, default="[]")
    text_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embed_model: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), default="")
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
