"""Play Application — Campaign aggregate."""

from __future__ import annotations

import json
import logging
from typing import Any

from database import SessionLocal
from models.entities import Campaign, CampaignCharacter, Job

logger = logging.getLogger(__name__)


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
    return payload
