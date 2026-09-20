"""Player action intake — FIFO per GameSession + one exclusive GM flight."""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from typing import Any

from database import SessionLocal
from models.entities import GameSession, SessionPlayer
from services.play.gm.errors import ActionError
from services.play.gm.runtime import run_gm_flight
from services.play.gm.state import load_state
from services.play.gm.tools import DiceRng
from services.rate_limit import check_play_action_rate

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


def _pending_check(session_id: str) -> dict | None:
    db = SessionLocal()
    try:
        gs = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not gs:
            return None
        pending = load_state(gs.state_json).get("pending_check")
        return pending if isinstance(pending, dict) and pending else None
    finally:
        db.close()


def _enqueue(session_id: str, slot: dict[str, Any]) -> dict:
    done = slot["done"]
    with _meta:
        _queues[session_id].append(slot)

    with _locks[session_id]:
        while True:
            with _meta:
                if not _queues[session_id]:
                    break
                next_slot = _queues[session_id].popleft()
            try:
                next_slot["result"] = _process_slot(session_id, next_slot)
            except Exception as exc:  # noqa: BLE001
                next_slot["error"] = exc
            next_slot["done"].set()
            if next_slot is slot:
                continue

    if not done.wait(timeout=150):
        raise ActionError("timeout", "Timed out waiting for GameMasterRuntime")
    if slot["error"]:
        raise slot["error"]
    return slot["result"]


def _process_slot(session_id: str, slot: dict[str, Any]) -> dict:
    character_id = _validate_actor(slot["user_id"], session_id)
    kind = slot.get("kind") or "action"
    if kind == "confirm_roll":
        pending = _pending_check(session_id)
        if not pending:
            raise ActionError("not_ready", "No Roll Call is waiting")
        pending_id = (slot.get("pending_id") or "").strip()
        if pending_id and pending.get("id") != pending_id:
            raise ActionError("invalid", "Roll Call does not match")
        if pending.get("character_id") != character_id:
            raise ActionError("forbidden", "Only the targeted Character's Player can confirm this Roll Call")
        alts = pending.get("alternatives")
        chosen_skill = (slot.get("chosen_skill") or "").strip() or None
        chosen_index = slot.get("chosen_index")
        if isinstance(alts, list) and len(alts) > 1 and not chosen_skill and chosen_index is None:
            raise ActionError(
                "needs_choice",
                "Choose which check to roll.",
            )
        return run_gm_flight(
            session_id,
            slot["user_id"],
            character_id,
            slot.get("text") or "SYSTEM:ROLL_CONFIRMED",
            llm=slot["llm"],
            dice_rng=slot["dice_rng"],
            retrieve_fn=slot.get("retrieve_fn"),
            tts=slot.get("tts"),
            speak=bool(slot.get("speak", True)),
            purpose="roll_resolution",
            pending_id=pending.get("id"),
            chosen_skill=chosen_skill,
            chosen_index=chosen_index,
        )

    pending = _pending_check(session_id)
    if pending:
        raise ActionError(
            "awaiting_roll",
            "A Roll Call is pending; the targeted player must confirm it first.",
        )
    return run_gm_flight(
        session_id,
        slot["user_id"],
        character_id,
        slot["text"],
        llm=slot["llm"],
        dice_rng=slot["dice_rng"],
        retrieve_fn=slot.get("retrieve_fn"),
        tts=slot.get("tts"),
        speak=bool(slot.get("speak", True)),
    )


def submit_player_action(
    user_id: str,
    session_id: str,
    text: str,
    llm: Any | None = None,
    dice_rng: DiceRng | None = None,
    tts: Any | None = None,
    speak: bool = True,
    retrieve_fn=None,
) -> dict:
    action_text = (text or "").strip()
    if not action_text:
        raise ActionError("invalid", "Action text is required")

    if not check_play_action_rate(user_id):
        raise ActionError("rate_limited", "Too many actions; slow down a moment")

    # Membership/character checks run under the session lock only. A pre-lock DB
    # round-trip races on SQLite StaticPool when two threads open SessionLocal.

    slot: dict[str, Any] = {
        "kind": "action",
        "user_id": user_id,
        "text": action_text,
        "llm": llm,
        "dice_rng": dice_rng,
        "retrieve_fn": retrieve_fn,
        "tts": tts,
        "speak": speak,
        "result": None,
        "error": None,
        "done": threading.Event(),
    }
    return _enqueue(session_id, slot)


def confirm_roll(
    user_id: str,
    session_id: str,
    pending_id: str | None = None,
    llm: Any | None = None,
    dice_rng: DiceRng | None = None,
    tts: Any | None = None,
    speak: bool = True,
    retrieve_fn=None,
    chosen_skill: str | None = None,
    chosen_index: int | None = None,
) -> dict:
    if not check_play_action_rate(user_id):
        raise ActionError("rate_limited", "Too many actions; slow down a moment")

    slot: dict[str, Any] = {
        "kind": "confirm_roll",
        "user_id": user_id,
        "text": "SYSTEM:ROLL_CONFIRMED",
        "pending_id": (pending_id or "").strip(),
        "chosen_skill": (chosen_skill or "").strip() or None,
        "chosen_index": chosen_index,
        "llm": llm,
        "dice_rng": dice_rng,
        "retrieve_fn": retrieve_fn,
        "tts": tts,
        "speak": speak,
        "result": None,
        "error": None,
        "done": threading.Event(),
    }
    return _enqueue(session_id, slot)
