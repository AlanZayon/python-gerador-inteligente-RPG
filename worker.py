"""
Worker for async RPG campaign processing.

Uses reliable queue pattern: BRPOPLPUSH from priority/pending -> processing, LREM on ack.
Run with: python worker.py
Batch mode (GHA): MAX_JOBS=5 python worker.py
"""

import logging
import os
import time
from datetime import datetime

import redis
from dotenv import load_dotenv

from database import init_db
from services.email import send_campaign_complete_email
from services.job_status import get_status, mark_failed, save_result, save_status
from services.jobs_db import update_job_status
from services.quota import refund_credits
from services.redis_client import (
    PENDING_JOBS_QUEUE,
    PRIORITY_JOBS_QUEUE,
    PROCESSING_JOBS_QUEUE,
    create_redis_client,
)
from services.s3_storage import delete_s3_object
from services.auth import validate_production_auth_config
from services.sentry_init import init_sentry
from services.users import get_user_by_id
from tasks.campaign_tasks import process_campaign_generation

load_dotenv()
validate_production_auth_config()
init_sentry(with_flask=False)

try:
    init_db()
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = float(os.getenv("WORKER_POLL_INTERVAL", "2"))
MAX_JOBS = int(os.getenv("MAX_JOBS", "0"))
INPUT_DELETE_AFTER_PROCESS = os.getenv("S3_DELETE_INPUTS_AFTER_PROCESS", "true").lower() == "true"


def dequeue_job(conn) -> str | None:
    """Pop from priority queue first, then standard pending queue."""
    for source in (PRIORITY_JOBS_QUEUE, PENDING_JOBS_QUEUE):
        job_id = conn.brpoplpush(source, PROCESSING_JOBS_QUEUE, timeout=1)
        if job_id:
            if isinstance(job_id, bytes):
                return job_id.decode("utf-8")
            return job_id
    return None


def ack_job(conn, job_id: str) -> None:
    conn.lrem(PROCESSING_JOBS_QUEUE, 1, job_id)


def wait_for_job(conn):
    while True:
        job_id = dequeue_job(conn)
        if job_id:
            return job_id
        if MAX_JOBS > 0:
            return None
        time.sleep(POLL_INTERVAL_SECONDS)


def process_job(conn, job_id: str) -> None:
    job_key = f"rpg:job:{job_id}"
    job_data_raw = conn.hgetall(job_key)

    if not job_data_raw:
        logger.warning("Job %s not found in Redis.", job_id)
        ack_job(conn, job_id)
        return

    job_data = {
        (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
        for k, v in job_data_raw.items()
    }

    user_id = job_data.get("user_id")
    credits_charged = int(job_data.get("credits_charged") or 0)
    input_s3_key = job_data.get("s3_key")

    conn.hset(
        job_key,
        mapping={
            "status": "processing",
            "processed_at": datetime.utcnow().isoformat(),
        },
    )
    save_status(job_id, "processing", {"progress": "Starting processing..."}, conn=conn)

    try:
        result = process_campaign_generation(
            job_id=job_id,
            file_url=job_data["file_url"],
            filename=job_data["filename"],
            target_language=job_data.get("language", "en"),
            campaign_complexity=job_data.get("complexity", "mediana"),
            system_preset=job_data.get("system_preset"),
            party_level=job_data.get("party_level", ""),
            tone=job_data.get("tone", ""),
            theme=job_data.get("theme", ""),
        )

        if result:
            save_result(job_id, result, conn=conn)
            conn.hset(job_key, "status", "completed")
            campaign_s3_key = result.get("s3_key")
            update_job_status(job_id, "completed", campaign_s3_key=campaign_s3_key, s3_key=input_s3_key)

            if user_id:
                user = get_user_by_id(user_id)
                if user and user.email:
                    campaign_url = result.get("campaign_url", "")
                    send_campaign_complete_email(user.email, job_id, campaign_url)

            if INPUT_DELETE_AFTER_PROCESS and input_s3_key:
                delete_s3_object(input_s3_key)

            logger.info("Job %s completed successfully.", job_id)
            ack_job(conn, job_id)
            return

        _fail_job(conn, job_id, user_id, credits_charged, "Empty result")
    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        _fail_job(conn, job_id, user_id, credits_charged, str(exc))


def _fail_job(conn, job_id: str, user_id: str | None, credits_charged: int, reason: str) -> None:
    if credits_charged > 0 and user_id:
        reason = f"{reason} Credits refunded automatically."
    mark_failed(job_id, reason, conn=conn)
    conn.hset(f"rpg:job:{job_id}", "status", "failed")
    update_job_status(job_id, "failed")
    if user_id and credits_charged > 0:
        refund_credits(user_id, credits_charged, job_id)
    ack_job(conn, job_id)


def recover_stale_processing_jobs(conn) -> None:
    """Requeue jobs left in the processing queue after a worker crash."""
    items = conn.lrange(PROCESSING_JOBS_QUEUE, 0, -1) or []
    if not items:
        return

    logger.info("Recovering %s job(s) from processing queue", len(items))
    status_conn = create_redis_client(decode_responses=False)

    for raw_id in items:
        job_id = raw_id.decode() if isinstance(raw_id, bytes) else raw_id
        conn.lrem(PROCESSING_JOBS_QUEUE, 1, raw_id)
        status_data = get_status(job_id, conn=status_conn)
        if not status_data:
            logger.warning("Removing orphaned processing entry: %s", job_id)
            continue
        st = status_data.get("status")
        if st in ("completed", "failed"):
            logger.info("Removing stale processing entry for %s (status=%s)", job_id, st)
            continue
        logger.info("Requeueing stuck job %s (status=%s)", job_id, st)
        conn.lpush(PENDING_JOBS_QUEUE, job_id)


def run_worker() -> None:
    conn = create_redis_client(decode_responses=False)
    conn.ping()
    recover_stale_processing_jobs(conn)
    jobs_processed = 0
    logger.info(
        "Worker connected. Queues: %s (priority), %s (standard). MAX_JOBS=%s",
        PRIORITY_JOBS_QUEUE,
        PENDING_JOBS_QUEUE,
        MAX_JOBS or "unlimited",
    )

    while True:
        try:
            job_id = wait_for_job(conn)
            if job_id is None:
                logger.info("No pending jobs. Batch worker exiting.")
                break

            logger.info("Processing job: %s", job_id)
            process_job(conn, job_id)

            jobs_processed += 1
            if MAX_JOBS > 0 and jobs_processed >= MAX_JOBS:
                logger.info("MAX_JOBS=%s reached. Exiting.", MAX_JOBS)
                break

        except (redis.ConnectionError, redis.TimeoutError) as exc:
            logger.warning("Redis unavailable (%s). Reconnecting in 5s...", exc)
            time.sleep(5)
            conn = create_redis_client(decode_responses=False)
        except KeyboardInterrupt:
            logger.info("Worker stopped by user.")
            break


if __name__ == "__main__":
    run_worker()
