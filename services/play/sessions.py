"""Play Application — GameSession lobby."""

from __future__ import annotations

import secrets
import string
from datetime import datetime

from database import SessionLocal
from models.entities import Campaign, CampaignCharacter, GameSession, SessionPlayer

MIN_PLAYERS = 2
MAX_PLAYERS = 4
ACTIVE_STATUSES = ("LOBBY", "STARTING", "ACTIVE", "PAUSED")


class SessionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _player_count(db, session_id: str) -> int:
    return db.query(SessionPlayer).filter(SessionPlayer.game_session_id == session_id).count()


def _get_membership(db, session_id: str, user_id: str) -> SessionPlayer | None:
    return (
        db.query(SessionPlayer)
        .filter(SessionPlayer.game_session_id == session_id, SessionPlayer.user_id == user_id)
        .first()
    )


def create_game_session(user_id: str, campaign_id: str) -> GameSession:
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign or campaign.host_user_id != user_id:
            raise SessionError("not_found", "Campaign not found")

        existing = (
            db.query(GameSession)
            .filter(
                GameSession.campaign_id == campaign_id,
                GameSession.status.in_(ACTIVE_STATUSES),
            )
            .first()
        )
        if existing:
            raise SessionError("session_exists", "Campaign already has an active GameSession")

        code = _invite_code()
        while db.query(GameSession).filter(GameSession.invite_code == code).first():
            code = _invite_code()

        gs = GameSession(
            campaign_id=campaign_id,
            invite_code=code,
            status="LOBBY",
            host_user_id=user_id,
            state_json="{}",
        )
        db.add(gs)
        db.flush()
        db.add(
            SessionPlayer(
                game_session_id=gs.id,
                user_id=user_id,
                role="host",
                ready=False,
                connected=True,
            )
        )
        db.commit()
        db.refresh(gs)
        return gs
    except SessionError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def join_game_session(user_id: str, invite_code: str) -> SessionPlayer:
    db = SessionLocal()
    try:
        code = (invite_code or "").strip().upper()
        gs = db.query(GameSession).filter(GameSession.invite_code == code).first()
        if not gs or gs.status != "LOBBY":
            raise SessionError("not_found", "Invite not found or lobby closed")

        existing = _get_membership(db, gs.id, user_id)
        if existing:
            return existing

        if _player_count(db, gs.id) >= MAX_PLAYERS:
            raise SessionError("full", "GameSession is full (max 4 players)")

        sp = SessionPlayer(
            game_session_id=gs.id,
            user_id=user_id,
            role="player",
            ready=False,
            connected=True,
        )
        db.add(sp)
        db.commit()
        db.refresh(sp)
        return sp
    except SessionError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def claim_character(user_id: str, session_id: str, character_id: str) -> SessionPlayer:
    db = SessionLocal()
    try:
        gs = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not gs or gs.status != "LOBBY":
            raise SessionError("not_found", "GameSession not in lobby")

        membership = _get_membership(db, session_id, user_id)
        if not membership:
            raise SessionError("forbidden", "Not a member of this GameSession")

        character = (
            db.query(CampaignCharacter)
            .filter(
                CampaignCharacter.id == character_id,
                CampaignCharacter.campaign_id == gs.campaign_id,
            )
            .first()
        )
        if not character or not character.claimable:
            raise SessionError("not_found", "Character not available")

        taken = (
            db.query(SessionPlayer)
            .filter(
                SessionPlayer.game_session_id == session_id,
                SessionPlayer.character_id == character_id,
            )
            .first()
        )
        if taken and taken.user_id != user_id:
            raise SessionError("character_taken", "Character already claimed")

        membership.character_id = character_id
        membership.ready = False
        db.commit()
        db.refresh(membership)
        return membership
    except SessionError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def set_ready(user_id: str, session_id: str, ready: bool = True) -> SessionPlayer:
    db = SessionLocal()
    try:
        gs = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not gs or gs.status != "LOBBY":
            raise SessionError("not_found", "GameSession not in lobby")
        membership = _get_membership(db, session_id, user_id)
        if not membership:
            raise SessionError("forbidden", "Not a member of this GameSession")
        if ready and not membership.character_id:
            raise SessionError("not_ready", "Claim a Character before ready")
        membership.ready = bool(ready)
        db.commit()
        db.refresh(membership)
        return membership
    except SessionError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def start_game_session(user_id: str, session_id: str) -> GameSession:
    db = SessionLocal()
    try:
        gs = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not gs:
            raise SessionError("not_found", "GameSession not found")
        if gs.host_user_id != user_id:
            raise SessionError("forbidden", "Only the host can start")
        if gs.status != "LOBBY":
            raise SessionError("not_ready", "GameSession is not in lobby")

        players = (
            db.query(SessionPlayer).filter(SessionPlayer.game_session_id == session_id).all()
        )
        if not (MIN_PLAYERS <= len(players) <= MAX_PLAYERS):
            raise SessionError(
                "not_ready",
                f"Need {MIN_PLAYERS}–{MAX_PLAYERS} players to start",
            )
        if any(not p.character_id for p in players):
            raise SessionError("not_ready", "Every player must claim a Character")
        claimed = [p.character_id for p in players]
        if len(claimed) != len(set(claimed)):
            raise SessionError("not_ready", "Character claims must be unique")
        if any(not p.ready for p in players):
            raise SessionError("not_ready", "Every player must be ready")

        gs.status = "ACTIVE"
        gs.started_at = datetime.utcnow()
        db.commit()
        db.refresh(gs)
        return gs
    except SessionError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def end_game_session(user_id: str, session_id: str) -> GameSession:
    db = SessionLocal()
    try:
        gs = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not gs:
            raise SessionError("not_found", "GameSession not found")
        if gs.host_user_id != user_id:
            raise SessionError("forbidden", "Only the host can end the session")
        if gs.status == "ENDED":
            return gs
        gs.status = "ENDED"
        gs.ended_at = datetime.utcnow()
        db.commit()
        db.refresh(gs)
        return gs
    except SessionError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_session_for_user(user_id: str, session_id: str) -> GameSession | None:
    db = SessionLocal()
    try:
        gs = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not gs:
            return None
        if not _get_membership(db, session_id, user_id):
            return None
        return gs
    finally:
        db.close()


def session_to_dict(gs: GameSession) -> dict:
    db = SessionLocal()
    try:
        players = (
            db.query(SessionPlayer)
            .filter(SessionPlayer.game_session_id == gs.id)
            .order_by(SessionPlayer.created_at)
            .all()
        )
        campaign = db.query(Campaign).filter(Campaign.id == gs.campaign_id).first()
        chars = (
            db.query(CampaignCharacter)
            .filter(CampaignCharacter.campaign_id == gs.campaign_id)
            .order_by(CampaignCharacter.sort_order)
            .all()
        )
        claimed = {p.character_id: p.user_id for p in players if p.character_id}
        return {
            "id": gs.id,
            "campaign_id": gs.campaign_id,
            "campaign_title": campaign.title if campaign else "",
            "invite_code": gs.invite_code,
            "status": gs.status,
            "host_user_id": gs.host_user_id,
            "created_at": gs.created_at.isoformat() if gs.created_at else None,
            "started_at": gs.started_at.isoformat() if gs.started_at else None,
            "ended_at": gs.ended_at.isoformat() if gs.ended_at else None,
            "players": [
                {
                    "id": p.id,
                    "user_id": p.user_id,
                    "character_id": p.character_id,
                    "role": p.role,
                    "ready": p.ready,
                    "connected": p.connected,
                }
                for p in players
            ],
            "characters": [
                {
                    "id": c.id,
                    "display_name": c.display_name,
                    "claimable": c.claimable,
                    "claimed_by": claimed.get(c.id),
                    "sort_order": c.sort_order,
                }
                for c in chars
            ],
        }
    finally:
        db.close()
