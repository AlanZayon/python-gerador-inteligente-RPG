import os

import redis
from dotenv import load_dotenv

from services.queue_constants import (
    PENDING_JOBS_QUEUE,
    PRIORITY_JOBS_QUEUE,
    PROCESSING_JOBS_QUEUE,
)

load_dotenv()

__all__ = [
    "PENDING_JOBS_QUEUE",
    "PRIORITY_JOBS_QUEUE",
    "PROCESSING_JOBS_QUEUE",
    "get_redis_url",
    "create_redis_client",
]


def get_redis_url() -> str:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return url.strip().strip('"').strip("'")


def create_redis_client(decode_responses: bool = True) -> redis.Redis:
    return redis.from_url(
        get_redis_url(),
        decode_responses=decode_responses,
        socket_connect_timeout=10,
    )
