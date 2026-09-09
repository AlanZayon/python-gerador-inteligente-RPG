"""Add memories table for session / campaign / character-private knowledge

Revision ID: 0007_memories
Revises: 0006_game_events
Create Date: 2026-09-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_memories"
down_revision: Union[str, None] = "0006_game_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("campaign_id", sa.String(length=36), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column(
            "game_session_id",
            sa.String(length=36),
            sa.ForeignKey("game_sessions.id"),
            nullable=True,
        ),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column(
            "character_id",
            sa.String(length=36),
            sa.ForeignKey("campaign_characters.id"),
            nullable=True,
        ),
        sa.Column("content_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_memories_campaign_id", "memories", ["campaign_id"])
    op.create_index("ix_memories_game_session_id", "memories", ["game_session_id"])
    op.create_index("ix_memories_character_id", "memories", ["character_id"])
    op.create_index("ix_memories_scope", "memories", ["scope"])


def downgrade() -> None:
    op.drop_table("memories")
