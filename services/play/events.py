"""Durable GameSession events + live hub publish."""

from __future__ import annotations

import json
from datetime import datetime

from models.entities import GameEvent
from services.play import hub as hub_module


def next_event_seq(db, session_id: str) -> int:
    last = (
        db.query(GameEvent)
        .filter(GameEvent.game_session_id == session_id)
        .order_by(GameEvent.seq.desc())
        .first()
    )
    return (last.seq if last else 0) + 1


def event_to_envelope(ev: GameEvent) -> dict:
    try:
        payload = json.loads(ev.payload_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "version": 1,
        "type": ev.type,
        "session_id": ev.game_session_id,
        "event_id": ev.id,
        "seq": ev.seq,
        "actor_id": ev.actor_id,
        "target_id": ev.target_id,
        "payload": payload,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


def record_event(
    db,
    *,
    session_id: str,
    event_type: str,
    payload: dict,
    actor_id: str | None = None,
    target_id: str | None = None,
) -> GameEvent:
    """Persist a GameEvent. Caller should publish after commit."""
    ev = GameEvent(
        game_session_id=session_id,
        seq=next_event_seq(db, session_id),
        type=event_type,
        actor_id=actor_id,
        target_id=target_id,
        payload_json=json.dumps(payload or {}, ensure_ascii=False),
        created_at=datetime.utcnow(),
    )
    db.add(ev)
    db.flush()
    return ev


def publish_event(ev: GameEvent) -> dict:
    envelope = event_to_envelope(ev)
    hub_module.default_hub.publish(ev.game_session_id, envelope)
    return envelope


def record_and_publish(
    db,
    *,
    session_id: str,
    event_type: str,
    payload: dict,
    actor_id: str | None = None,
    target_id: str | None = None,
    publish: bool = True,
) -> GameEvent:
    """Persist event; optionally publish immediately (prefer publish after commit)."""
    ev = record_event(
        db,
        session_id=session_id,
        event_type=event_type,
        payload=payload,
        actor_id=actor_id,
        target_id=target_id,
    )
    if publish:
        publish_event(ev)
    return ev
