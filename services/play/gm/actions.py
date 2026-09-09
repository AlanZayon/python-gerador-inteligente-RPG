"""Player action intake — exclusive per-GameSession GM flight (FIFO via lock)."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

from database import SessionLocal
from models.entities import GameSession, SessionPlayer
from services.play.gm.runtime import run_gm_flight
from services.play.gm.tools import DiceRng

_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


class ActionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def submit_player_action(
    user_id: str,
    session_id: str,
    text: str,
    llm: Any | None = None,
    dice_rng: DiceRng | None = None,
) -> dict:
    action_text = (text or "").strip()
    if not action_text:
        raise ActionError("invalid", "Action text is required")

    db = SessionLocal()
    try:
        gs = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not gs:
            raise ActionError("not_found", "GameSession not found")
        if gs.status != "ACTIVE":
            raise ActionError("not_ready", "GameSession is not ACTIVE")

        membership = (
            db.query(SessionPlayer)
            .filter(
                SessionPlayer.game_session_id == session_id,
                SessionPlayer.user_id == user_id,
            )
            .first()
        )
        if not membership:
            raise ActionError("forbidden", "Not a member of this GameSession")
        if not membership.character_id:
            raise ActionError("not_ready", "Claim a Character before acting")
        character_id = membership.character_id
    finally:
        db.close()

    with _locks[session_id]:
        return run_gm_flight(
            session_id,
            user_id,
            character_id,
            action_text,
            llm=llm,
            dice_rng=dice_rng,
        )
