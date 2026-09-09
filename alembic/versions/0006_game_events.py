"""Add game_events for GM turn audit log

Revision ID: 0006_game_events
Revises: 0005_lobby_uniqueness
Create Date: 2026-09-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_game_events"
down_revision: Union[str, None] = "0005_lobby_uniqueness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "game_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "game_session_id",
            sa.String(length=36),
            sa.ForeignKey("game_sessions.id"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_game_events_game_session_id", "game_events", ["game_session_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_game_event_seq ON game_events (game_session_id, seq)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_game_event_seq")
    op.drop_table("game_events")
