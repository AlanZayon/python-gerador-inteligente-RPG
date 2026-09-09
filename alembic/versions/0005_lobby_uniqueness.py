"""Lobby uniqueness constraints for concurrent claim/create safety

Revision ID: 0005_lobby_uniqueness
Revises: 0004_game_sessions
Create Date: 2026-09-09
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005_lobby_uniqueness"
down_revision: Union[str, None] = "0004_game_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_game_sessions_active_campaign "
        "ON game_sessions (campaign_id) "
        "WHERE status IN ('LOBBY', 'STARTING', 'ACTIVE', 'PAUSED')"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_session_player_user "
        "ON session_players (game_session_id, user_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_session_player_character "
        "ON session_players (game_session_id, character_id) "
        "WHERE character_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_session_player_character")
    op.execute("DROP INDEX IF EXISTS uq_session_player_user")
    op.execute("DROP INDEX IF EXISTS uq_game_sessions_active_campaign")
