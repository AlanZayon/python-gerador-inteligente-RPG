"""Reconnect snapshot and presence for GameSession sync."""

from __future__ import annotations

from database import SessionLocal
from models.entities import GameEvent, GameSession, SessionPlayer
from services.play.events import event_to_envelope, record_event
from services.play import hub as hub_module
from services.play.gm.state import load_state
from services.play.sessions import session_to_dict


class SyncError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _require_member(db, user_id: str, session_id: str) -> tuple[GameSession, SessionPlayer]:
    gs = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not gs:
        raise SyncError("not_found", "GameSession not found")
    membership = (
        db.query(SessionPlayer)
        .filter(SessionPlayer.game_session_id == session_id, SessionPlayer.user_id == user_id)
        .first()
    )
    if not membership:
        raise SyncError("forbidden", "Not a member of this GameSession")
    return gs, membership


def get_reconnect_snapshot(user_id: str, session_id: str, after_seq: int = 0) -> dict:
    db = SessionLocal()
    try:
        gs, _membership = _require_member(db, user_id, session_id)
        events = (
            db.query(GameEvent)
            .filter(GameEvent.game_session_id == session_id, GameEvent.seq > int(after_seq or 0))
            .order_by(GameEvent.seq)
            .all()
        )
        players = (
            db.query(SessionPlayer)
            .filter(SessionPlayer.game_session_id == session_id)
            .order_by(SessionPlayer.created_at)
            .all()
        )
        last = (
            db.query(GameEvent)
            .filter(GameEvent.game_session_id == session_id)
            .order_by(GameEvent.seq.desc())
            .first()
        )
        return {
            "session": session_to_dict(gs),
            "state": load_state(gs.state_json),
            "state_version": gs.state_version,
            "events": [event_to_envelope(e) for e in events],
            "presence": [
                {"user_id": p.user_id, "connected": bool(p.connected), "role": p.role}
                for p in players
            ],
            "last_seq": last.seq if last else 0,
        }
    finally:
        db.close()


def set_presence(user_id: str, session_id: str, connected: bool) -> dict:
    db = SessionLocal()
    try:
        gs, membership = _require_member(db, user_id, session_id)
        membership.connected = bool(connected)
        event_type = "presence_up" if connected else "presence_down"
        ev = record_event(
            db,
            session_id=gs.id,
            event_type=event_type,
            payload={"user_id": user_id, "connected": bool(connected)},
            actor_id=user_id,
        )
        envelope = event_to_envelope(ev)
        db.commit()
        hub_module.default_hub.publish(session_id, envelope)
        return {
            "user_id": user_id,
            "connected": bool(connected),
            "session_id": session_id,
        }
    except SyncError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
