"""Player action intake — FIFO per GameSession + one exclusive GM flight."""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from typing import Any

from database import SessionLocal
from models.entities import GameSession, SessionPlayer
from services.play.gm.errors import ActionError
from services.play.gm.runtime import run_gm_flight
from services.play.gm.tools import DiceRng

_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_queues: dict[str, deque] = defaultdict(deque)
_meta = threading.Lock()


def _validate_actor(user_id: str, session_id: str) -> str:
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
        return membership.character_id
    finally:
        db.close()


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

    # Fast pre-check (also re-checked under the session lock before flight).
    _validate_actor(user_id, session_id)

    done = threading.Event()
    slot: dict[str, Any] = {
        "user_id": user_id,
        "text": action_text,
        "llm": llm,
        "dice_rng": dice_rng,
        "result": None,
        "error": None,
        "done": done,
    }
    with _meta:
        _queues[session_id].append(slot)

    with _locks[session_id]:
        while True:
            with _meta:
                if not _queues[session_id]:
                    break
                next_slot = _queues[session_id].popleft()
            try:
                character_id = _validate_actor(next_slot["user_id"], session_id)
                next_slot["result"] = run_gm_flight(
                    session_id,
                    next_slot["user_id"],
                    character_id,
                    next_slot["text"],
                    llm=next_slot["llm"],
                    dice_rng=next_slot["dice_rng"],
                )
            except Exception as exc:  # noqa: BLE001
                next_slot["error"] = exc
            next_slot["done"].set()
            if next_slot is slot:
                # Keep draining so later enqueued actions are not stranded if their
                # threads are waiting on our lock holder.
                continue

    if not done.wait(timeout=120):
        raise ActionError("timeout", "Timed out waiting for GameMasterRuntime")
    if slot["error"]:
        raise slot["error"]
    return slot["result"]
