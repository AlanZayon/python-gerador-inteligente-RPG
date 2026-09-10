"""Play Application — Campaign aggregate."""

from __future__ import annotations

import json
import logging
from typing import Any

from database import SessionLocal
from models.entities import Campaign, CampaignCharacter, Job

logger = logging.getLogger(__name__)

# Keep in sync with services.play.sessions.MAX_PLAYERS — table seats need claimable PCs.
MIN_CLAIMABLE_ROSTER = 4


class CampaignCreateError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _parse_sheets(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [s for s in data if isinstance(s, dict)]
    return []


def ensure_claimable_roster(db, campaign_id: str, minimum: int = MIN_CLAIMABLE_ROSTER) -> int:
    """Pad Campaign with generic claimable PCs so 2–4 players can sit.

    Returns how many characters were added.
    """
    existing = (
        db.query(CampaignCharacter)
        .filter(CampaignCharacter.campaign_id == campaign_id)
        .order_by(CampaignCharacter.sort_order)
        .all()
    )
    added = 0
    next_order = (existing[-1].sort_order + 1) if existing else 0
    while len(existing) + added < minimum:
        idx = len(existing) + added + 1
        db.add(
            CampaignCharacter(
                campaign_id=campaign_id,
                display_name=f"Adventurer {idx}",
                sheet_json=json.dumps(
                    {"name": f"Adventurer {idx}", "class": "Adventurer", "level": 1},
                    ensure_ascii=False,
                ),
                sort_order=next_order,
                claimable=True,
            )
        )
        next_order += 1
        added += 1
    if added:
        db.flush()
    return added


def _title_from_blueprint(blueprint: dict[str, Any], fallback: str = "Untitled Campaign") -> str:
    title = (blueprint.get("title") or "").strip()
    return title or fallback


def create_campaign_from_job(user_id: str, job_id: str) -> Campaign:
    """Create a playable Campaign from a completed Job owned by the user.

    Idempotent: if a Campaign already exists for this Job and host, return it.
    Does not create a GameSession.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job or job.user_id != user_id:
            raise CampaignCreateError("not_found", "Job not found")
        if job.status != "completed":
            raise CampaignCreateError("job_not_ready", "Job is not completed")
        if not job.blueprint_json:
            raise CampaignCreateError(
                "missing_blueprint",
                "Job has no Campaign Blueprint seed; cannot create a playable Campaign",
            )

        existing = (
            db.query(Campaign)
            .filter(Campaign.job_id == job_id, Campaign.host_user_id == user_id)
            .first()
        )
        if existing:
            ensure_claimable_roster(db, existing.id)
            db.commit()
            db.refresh(existing)
            return existing

        try:
            blueprint = json.loads(job.blueprint_json)
        except json.JSONDecodeError as exc:
            raise CampaignCreateError("missing_blueprint", "Blueprint seed is invalid JSON") from exc
        if not isinstance(blueprint, dict):
            raise CampaignCreateError("missing_blueprint", "Blueprint seed must be an object")

        campaign = Campaign(
            job_id=job.id,
            host_user_id=user_id,
            book_id=job.book_id,
            title=_title_from_blueprint(blueprint),
            blueprint_json=job.blueprint_json,
            manuscript_s3_key=job.campaign_s3_key,
            status="ready",
        )
        db.add(campaign)
        db.flush()

        for i, sheet in enumerate(_parse_sheets(job.character_sheets)):
            name = (sheet.get("name") or f"Character {i + 1}").strip() or f"Character {i + 1}"
            db.add(
                CampaignCharacter(
                    campaign_id=campaign.id,
                    display_name=name,
                    sheet_json=json.dumps(sheet, ensure_ascii=False),
                    sort_order=i,
                    claimable=True,
                )
            )

        ensure_claimable_roster(db, campaign.id)
        db.commit()
        db.refresh(campaign)
        logger.info("Created Campaign %s from Job %s", campaign.id, job_id)
        return campaign
    except CampaignCreateError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_campaign_for_user(user_id: str, campaign_id: str) -> Campaign | None:
    db = SessionLocal()
    try:
        return (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id, Campaign.host_user_id == user_id)
            .first()
        )
    finally:
        db.close()


def list_characters(campaign_id: str) -> list[CampaignCharacter]:
    db = SessionLocal()
    try:
        return (
            db.query(CampaignCharacter)
            .filter(CampaignCharacter.campaign_id == campaign_id)
            .order_by(CampaignCharacter.sort_order)
            .all()
        )
    finally:
        db.close()


def campaign_to_dict(campaign: Campaign) -> dict[str, Any]:
    from models.entities import GameSession
    from services.play.sessions import ACTIVE_STATUSES

    payload: dict[str, Any] = {
        "id": campaign.id,
        "job_id": campaign.job_id,
        "host_user_id": campaign.host_user_id,
        "book_id": campaign.book_id,
        "title": campaign.title,
        "status": campaign.status,
        "manuscript_s3_key": campaign.manuscript_s3_key,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
    }
    try:
        payload["blueprint"] = json.loads(campaign.blueprint_json or "{}")
    except json.JSONDecodeError:
        payload["blueprint"] = {}

    chars = list_characters(campaign.id)
    payload["characters"] = [
        {
            "id": c.id,
            "display_name": c.display_name,
            "claimable": c.claimable,
            "sort_order": c.sort_order,
            "sheet": json.loads(c.sheet_json or "{}"),
        }
        for c in chars
    ]

    db = SessionLocal()
    try:
        gs = (
            db.query(GameSession)
            .filter(
                GameSession.campaign_id == campaign.id,
                GameSession.status.in_(ACTIVE_STATUSES),
            )
            .order_by(GameSession.created_at.desc())
            .first()
        )
        payload["active_session"] = (
            {
                "id": gs.id,
                "invite_code": gs.invite_code,
                "status": gs.status,
            }
            if gs
            else None
        )
    finally:
        db.close()
    return payload
