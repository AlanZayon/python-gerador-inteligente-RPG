"""Redis-backed rate limiting with in-memory fallback."""

import os
import time
from collections import defaultdict
from functools import wraps
from threading import Lock

from flask import g, jsonify, request

from services.redis_client import create_redis_client

_memory_store: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))
_memory_lock = Lock()


def clear_memory_rate_limits() -> None:
    """Test helper — reset in-memory buckets."""
    with _memory_lock:
        _memory_store.clear()


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


def check_keyed_rate_limit(key: str, max_calls: int, window: int) -> bool:
    """Return True if allowed. Uses Redis when available, else memory."""
    if (os.getenv("RATE_LIMIT_BACKEND") or "").strip().lower() == "memory":
        return _memory_rate_limit(key, max_calls, window)
    try:
        import redis as redis_lib

        from services.redis_client import get_redis_url

        conn = redis_lib.from_url(
            get_redis_url(),
            decode_responses=True,
            socket_connect_timeout=0.4,
            socket_timeout=0.4,
        )
        count = conn.incr(key)
        if count == 1:
            conn.expire(key, window)
        return count <= max_calls
    except Exception:
        return _memory_rate_limit(key, max_calls, window)


def check_play_rate(user_id: str, *, kind: str) -> bool:
    if kind == "voice":
        max_calls = int(os.getenv("PLAY_VOICE_RATE_MAX") or "20")
        window = int(os.getenv("PLAY_VOICE_RATE_WINDOW") or "60")
        prefix = "rl:play_voice"
    else:
        max_calls = int(os.getenv("PLAY_ACTION_RATE_MAX") or "30")
        window = int(os.getenv("PLAY_ACTION_RATE_WINDOW") or "60")
        prefix = "rl:play_action"
    return check_keyed_rate_limit(f"{prefix}:user:{user_id}", max_calls, window)


def check_play_action_rate(user_id: str) -> bool:
    return check_play_rate(user_id, kind="action")


def check_play_voice_rate(user_id: str) -> bool:
    return check_play_rate(user_id, kind="voice")


def redis_rate_limit(max_calls: int = 10, window: int = 60, prefix: str = "rl"):
    """Rate limit using Redis INCR + EXPIRE, with in-memory fallback."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{prefix}:{_client_key()}"
            allowed = check_keyed_rate_limit(key, max_calls, window)
            if not allowed:
                return jsonify(
                    {"error": "Too many requests. Please try again shortly."}
                ), 429
            return func(*args, **kwargs)

        return wrapper

    return decorator
