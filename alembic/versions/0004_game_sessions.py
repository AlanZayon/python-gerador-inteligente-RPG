"""Add game_sessions and session_players for lobby

Revision ID: 0004_game_sessions
Revises: 0003_campaigns
Create Date: 2026-09-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_game_sessions"
down_revision: Union[str, None] = "0003_campaigns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "game_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("invite_code", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="LOBBY"),
        sa.Column("host_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_scene", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_game_sessions_campaign_id", "game_sessions", ["campaign_id"])
    op.create_index("ix_game_sessions_invite_code", "game_sessions", ["invite_code"], unique=True)
    op.create_index("ix_game_sessions_host_user_id", "game_sessions", ["host_user_id"])

    op.create_table(
        "session_players",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "game_session_id",
            sa.String(length=36),
            sa.ForeignKey("game_sessions.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "character_id",
            sa.String(length=36),
            sa.ForeignKey("campaign_characters.id"),
            nullable=True,
        ),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="player"),
        sa.Column("ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("connected", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_session_players_game_session_id", "session_players", ["game_session_id"])
    op.create_index("ix_session_players_user_id", "session_players", ["user_id"])


def downgrade() -> None:
    op.drop_table("session_players")
    op.drop_table("game_sessions")
