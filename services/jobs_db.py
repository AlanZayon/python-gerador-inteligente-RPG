"""Persist and query jobs in PostgreSQL."""

from datetime import datetime

from database import SessionLocal
from models.entities import Job


def find_idempotent_job(user_id: str, idempotency_key: str) -> Job | None:
    if not idempotency_key:
        return None
    db = SessionLocal()
    try:
        return (
            db.query(Job)
            .filter(Job.user_id == user_id, Job.idempotency_key == idempotency_key)
            .first()
        )
    finally:
        db.close()


def create_job_record(
    job_id: str,
    user_id: str,
    complexity: str,
    language: str,
    filename: str,
    credits_charged: int,
    idempotency_key: str | None = None,
    system_preset: str | None = None,
) -> Job:
    db = SessionLocal()
    try:
        if idempotency_key:
            existing = (
                db.query(Job)
                .filter(Job.user_id == user_id, Job.idempotency_key == idempotency_key)
                .first()
            )
            if existing:
                return existing
        job = Job(
            id=job_id,
            user_id=user_id,
            status="queued",
            complexity=complexity,
            language=language,
            filename=filename,
            credits_charged=credits_charged,
            idempotency_key=idempotency_key,
            system_preset=system_preset,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def update_job_status(
    job_id: str,
    status: str,
    campaign_s3_key: str | None = None,
    s3_key: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        job.status = status
        if campaign_s3_key:
            job.campaign_s3_key = campaign_s3_key
        if s3_key:
            job.s3_key = s3_key
        if status == "completed":
            job.completed_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def get_job_for_user(job_id: str, user_id: str | None) -> Job | None:
    db = SessionLocal()
    try:
        q = db.query(Job).filter(Job.id == job_id)
        if user_id:
            q = q.filter(Job.user_id == user_id)
        return q.first()
    finally:
        db.close()


def list_user_jobs(user_id: str, limit: int = 50) -> list[Job]:
    db = SessionLocal()
    try:
        return (
            db.query(Job)
            .filter(Job.user_id == user_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def get_job_by_share_slug(slug: str) -> Job | None:
    db = SessionLocal()
    try:
        return db.query(Job).filter(Job.share_slug == slug, Job.share_public.is_(True)).first()
    finally:
        db.close()


def set_job_share(job_id: str, user_id: str, slug: str, public: bool = True) -> bool:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
        if not job or job.status != "completed":
            return False
        job.share_slug = slug
        job.share_public = public
        db.commit()
        return True
    finally:
        db.close()
