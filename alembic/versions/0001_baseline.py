"""Baseline schema matching models.entities

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("clerk_id", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("plan", sa.String(length=32), nullable=False, server_default="free"),
        sa.Column("credits_balance", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("stripe_customer_id", sa.String(length=128), nullable=True),
        sa.Column("api_key_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_clerk_id", "users", ["clerk_id"], unique=True)

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("complexity", sa.String(length=32), nullable=False, server_default="mediana"),
        sa.Column("language", sa.String(length=8), nullable=False, server_default="en"),
        sa.Column("filename", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("s3_key", sa.String(length=512), nullable=True),
        sa.Column("campaign_s3_key", sa.String(length=512), nullable=True),
        sa.Column("credits_charged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("share_slug", sa.String(length=32), nullable=True),
        sa.Column("share_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("system_preset", sa.String(length=32), nullable=True),
        sa.Column("use_character_sheets", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("party_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("character_sheets", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_idempotency_key", "jobs", ["idempotency_key"])
    op.create_index("ix_jobs_share_slug", "jobs", ["share_slug"], unique=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(length=128), nullable=True),
        sa.Column("plan", sa.String(length=32), nullable=False, server_default="free"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("period_end", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_credit_transactions_user_id", "credit_transactions", ["user_id"])

    op.create_table(
        "book_indexes",
        sa.Column("book_id", sa.String(length=64), primary_key=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fingerprints_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("text_sha256", sa.String(length=64), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embed_model", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_book_indexes_sha256", "book_indexes", ["sha256"], unique=True)
    op.create_index("ix_book_indexes_text_sha256", "book_indexes", ["text_sha256"])

    op.create_table(
        "stripe_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stripe_events_event_id", "stripe_events", ["event_id"], unique=True)
    op.create_index("ix_stripe_events_session_id", "stripe_events", ["session_id"])


def downgrade() -> None:
    op.drop_table("stripe_events")
    op.drop_table("book_indexes")
    op.drop_table("credit_transactions")
    op.drop_table("subscriptions")
    op.drop_table("jobs")
    op.drop_table("users")
