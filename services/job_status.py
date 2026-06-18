"""Centralized job status storage in Redis."""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

from services.redis_client import create_redis_client

logger = logging.getLogger(__name__)

JOB_KEY_PREFIX = "rpg:job:"
DEFAULT_TTL_SECONDS = int(os.getenv("JOB_STATUS_TTL", str(7 * 24 * 3600)))


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def _result_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}:result"


def _decode_hash(raw: dict) -> dict[str, str]:
    return {
        (k.decode() if isinstance(k, bytes) else k): (
            v.decode() if isinstance(v, bytes) else v
        )
        for k, v in raw.items()
    }


def _get_conn(decode_responses: bool = True):
    return create_redis_client(decode_responses=decode_responses)


def save_status(
    job_id: str,
    status: str,
    data: Optional[dict[str, Any]] = None,
    conn=None,
) -> bool:
    """Persist job status, progress, error, and optional result fields in Redis."""
    try:
        redis_conn = conn or _get_conn(decode_responses=True)
        job_key = _job_key(job_id)
        now = datetime.utcnow().isoformat()

        mapping: dict[str, str] = {
            "status": status,
            "last_updated": now,
        }

        if data:
            if "progress" in data:
                mapping["progress"] = str(data["progress"])
            if "progress_percent" in data:
                mapping["progress_percent"] = str(data["progress_percent"])
            if "error" in data:
                mapping["error"] = str(data["error"])

            result_fields = {
                k: v
                for k, v in data.items()
                if k not in ("progress", "error")
            }
            if result_fields and status == "completed":
                str_result = {
                    k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    for k, v in result_fields.items()
                }
                redis_conn.hset(_result_key(job_id), mapping=str_result)
                redis_conn.expire(_result_key(job_id), DEFAULT_TTL_SECONDS)

        redis_conn.hset(job_key, mapping=mapping)
        redis_conn.expire(job_key, DEFAULT_TTL_SECONDS)
        return True
    except Exception as exc:
        logger.error("Erro ao salvar status do job %s: %s", job_id, exc)
        return False


def save_result(job_id: str, result: dict[str, Any], conn=None) -> bool:
    """Store completed job result hash."""
    try:
        redis_conn = conn or _get_conn(decode_responses=True)
        str_result = {
            k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            for k, v in result.items()
        }
        redis_conn.hset(_result_key(job_id), mapping=str_result)
        redis_conn.expire(_result_key(job_id), DEFAULT_TTL_SECONDS)
        return True
    except Exception as exc:
        logger.error("Erro ao salvar resultado do job %s: %s", job_id, exc)
        return False


def mark_failed(job_id: str, error: str, conn=None) -> bool:
    return save_status(job_id, "failed", {"error": error}, conn=conn)


def mark_processing(job_id: str, progress: str, progress_percent: int | None = None, conn=None) -> bool:
    data: dict[str, Any] = {"progress": progress}
    if progress_percent is not None:
        data["progress_percent"] = progress_percent
    return save_status(job_id, "processing", data, conn=conn)


def get_status(job_id: str, conn=None) -> Optional[dict[str, Any]]:
    """Return unified job status including progress, error, and result."""
    try:
        redis_conn = conn or _get_conn(decode_responses=False)
        job_key = _job_key(job_id)
        raw_data = redis_conn.hgetall(job_key)

        if not raw_data:
            return None

        status_data = _decode_hash(raw_data)

        if "status" not in status_data:
            return None

        result_raw = redis_conn.hgetall(_result_key(job_id))
        if result_raw:
            status_data["data"] = _decode_hash(result_raw)

        return status_data
    except Exception as exc:
        logger.exception("Erro ao buscar status do job %s: %s", job_id, exc)
        return None


def build_api_response(job_id: str, status_data: dict[str, Any]) -> dict[str, Any]:
    """Format job status for GET /job-status response."""
    last_updated = (
        status_data.get("last_updated")
        or status_data.get("processed_at")
        or status_data.get("created_at")
    )
    return {
        "job_id": job_id,
        "status": status_data.get("status", "unknown"),
        "progress": status_data.get("progress"),
        "progress_percent": int(status_data["progress_percent"])
        if status_data.get("progress_percent") and str(status_data["progress_percent"]).isdigit()
        else None,
        "error": status_data.get("error"),
        "last_updated": last_updated,
        "result": status_data.get("data"),
    }
