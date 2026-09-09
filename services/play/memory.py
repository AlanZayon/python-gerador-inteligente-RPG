"""Session, campaign, and character-private memory layers."""

from __future__ import annotations

import json
import re
from datetime import datetime

from database import SessionLocal
from models.entities import Memory

SCOPES = ("session", "campaign", "character_private")


class MemoryError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _to_dict(row: Memory) -> dict:
    try:
        payload = json.loads(row.content_json or "{}")
    except json.JSONDecodeError:
        payload = {"text": row.content_json}
    content = payload.get("text") if isinstance(payload, dict) else str(payload)
    if content is None and isinstance(payload, dict):
        content = json.dumps(payload, ensure_ascii=False)
    return {
        "id": row.id,
        "campaign_id": row.campaign_id,
        "game_session_id": row.game_session_id,
        "scope": row.scope,
        "character_id": row.character_id,
        "content": content or "",
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def write_memory(
    *,
    campaign_id: str,
    scope: str,
    content: str,
    game_session_id: str | None = None,
    character_id: str | None = None,
    db=None,
) -> dict:
    scope = (scope or "").strip()
    if scope not in SCOPES:
        raise MemoryError("invalid", f"scope must be one of {SCOPES}")
    if scope == "character_private" and not character_id:
        raise MemoryError("invalid", "character_private memories require character_id")
    if scope == "session" and not game_session_id:
        raise MemoryError("invalid", "session memories require game_session_id")

    owns_db = db is None
    db = db or SessionLocal()
    try:
        row = Memory(
            campaign_id=campaign_id,
            game_session_id=game_session_id if scope == "session" else None,
            scope=scope,
            character_id=character_id if scope == "character_private" else None,
            content_json=json.dumps({"text": (content or "").strip()}, ensure_ascii=False),
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.flush()
        out = _to_dict(row)
        if owns_db:
            db.commit()
        return out
    except Exception:
        if owns_db:
            db.rollback()
        raise
    finally:
        if owns_db:
            db.close()


def list_memories_for_gm(
    *,
    campaign_id: str,
    game_session_id: str | None = None,
    limit: int = 50,
    db=None,
) -> list[dict]:
    """GM may know all truths for continuity."""
    owns_db = db is None
    db = db or SessionLocal()
    try:
        q = db.query(Memory).filter(Memory.campaign_id == campaign_id)
        rows = q.order_by(Memory.created_at.desc()).limit(limit * 3).all()
        out: list[dict] = []
        for row in rows:
            if row.scope == "campaign":
                out.append(_to_dict(row))
            elif row.scope == "session" and game_session_id and row.game_session_id == game_session_id:
                out.append(_to_dict(row))
            elif row.scope == "character_private":
                out.append(_to_dict(row))
            if len(out) >= limit:
                break
        return list(reversed(out))
    finally:
        if owns_db:
            db.close()


def filter_memories_for_character(
    *,
    campaign_id: str,
    character_id: str,
    game_session_id: str | None = None,
    limit: int = 50,
    db=None,
) -> list[dict]:
    """Player-facing filter: campaign + session + only this Character's private knowledge."""
    owns_db = db is None
    db = db or SessionLocal()
    try:
        rows = (
            db.query(Memory)
            .filter(Memory.campaign_id == campaign_id)
            .order_by(Memory.created_at.desc())
            .limit(limit * 3)
            .all()
        )
        out: list[dict] = []
        for row in rows:
            if row.scope == "campaign":
                out.append(_to_dict(row))
            elif row.scope == "session" and game_session_id and row.game_session_id == game_session_id:
                out.append(_to_dict(row))
            elif row.scope == "character_private" and row.character_id == character_id:
                out.append(_to_dict(row))
            if len(out) >= limit:
                break
        return list(reversed(out))
    finally:
        if owns_db:
            db.close()


def scrub_table_narration(narration: str, private_memories: list[dict]) -> str:
    """Scrub character-private secrets from table-wide GM narration."""
    text = narration or ""
    for mem in private_memories or []:
        secret = (mem.get("content") or "").strip()
        if len(secret) < 4:
            continue
        if secret in text:
            text = text.replace(secret, "[private knowledge withheld]")
        for token in re.findall(r"[A-Z0-9][A-Z0-9_-]{3,}", secret):
            if token in text:
                text = text.replace(token, "[redacted]")
    return text


# Back-compat alias used by earlier tests/call sites
filter_public_narration = scrub_table_narration
