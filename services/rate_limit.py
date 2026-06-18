"""Redis-backed rate limiting with in-memory fallback."""

import time
from collections import defaultdict
from functools import wraps
from threading import Lock

from flask import g, jsonify, request

from services.redis_client import create_redis_client

_memory_store: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))
_memory_lock = Lock()


def _client_key() -> str:
    user = getattr(g, "user", None)
    if user and getattr(user, "id", None):
        return f"user:{user.id}"
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"key:{api_key[:16]}"
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return f"bearer:{auth[7:16]}"
    return f"ip:{request.remote_addr or 'unknown'}"


def _memory_rate_limit(key: str, max_calls: int, window: int) -> bool:
    now = time.time()
    with _memory_lock:
        count, expires = _memory_store[key]
        if now > expires:
            _memory_store[key] = (1, now + window)
            return True
        if count >= max_calls:
            return False
        _memory_store[key] = (count + 1, expires)
        return True


def redis_rate_limit(max_calls: int = 10, window: int = 60, prefix: str = "rl"):
    """Rate limit using Redis INCR + EXPIRE, with in-memory fallback."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{prefix}:{_client_key()}"
            allowed = False
            try:
                conn = create_redis_client(decode_responses=True)
                count = conn.incr(key)
                if count == 1:
                    conn.expire(key, window)
                allowed = count <= max_calls
            except Exception:
                allowed = _memory_rate_limit(key, max_calls, window)
            if not allowed:
                return jsonify(
                    {"error": "Too many requests. Please try again shortly."}
                ), 429
            return func(*args, **kwargs)

        return wrapper

    return decorator
