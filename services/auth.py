"""Authentication: Clerk JWT, API keys, dev mode."""

import hashlib
import os
from functools import wraps

import jwt
import requests
from flask import g, jsonify, request

from database import SessionLocal
from models.entities import User

_jwks_cache = None


def _get_api_keys() -> set[str]:
    raw = os.getenv("API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}


def _auth_dev_mode() -> bool:
    return os.getenv("AUTH_DEV_MODE", "false").lower() == "true"


def _is_production() -> bool:
    return os.getenv("FLASK_ENV", "").lower() == "production"


def validate_production_auth_config() -> None:
    """Abort startup if production runs with dev auth bypass enabled."""
    if _is_production() and _auth_dev_mode():
        raise RuntimeError(
            "AUTH_DEV_MODE=true is forbidden when FLASK_ENV=production. "
            "Set AUTH_DEV_MODE=false and configure CLERK_JWKS_URL + CLERK_ISSUER."
        )


def _clerk_configured() -> bool:
    return bool(os.getenv("CLERK_JWKS_URL") or os.getenv("CLERK_ISSUER"))


def _get_jwks():
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    url = os.getenv("CLERK_JWKS_URL")
    if not url and os.getenv("CLERK_ISSUER"):
        url = f"{os.getenv('CLERK_ISSUER').rstrip('/')}/.well-known/jwks.json"
    if not url:
        return None
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    _jwks_cache = resp.json()
    return _jwks_cache


def _verify_clerk_token(token: str) -> dict | None:
    try:
        jwks = _get_jwks()
        if not jwks:
            return None
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if not key:
            return None
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        issuer = os.getenv("CLERK_ISSUER")
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
        return payload
    except Exception:
        return None


def get_bearer_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def _lookup_api_key_user(api_key: str) -> dict | None:
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.api_key_hash == key_hash).first()
        if user:
            return {"clerk_id": user.clerk_id, "email": user.email, "user_id": user.id}
    finally:
        db.close()
    return None


def resolve_auth_context() -> dict | None:
    """Return {clerk_id, email} or None."""
    token = get_bearer_token()
    if token:
        if _auth_dev_mode() and token == "dev-token":
            return {
                "clerk_id": os.getenv("AUTH_DEV_USER_ID", "dev-user-001"),
                "email": os.getenv("AUTH_DEV_EMAIL", "dev@arcane-forge.local"),
            }
        if _clerk_configured():
            payload = _verify_clerk_token(token)
            if payload:
                return {
                    "clerk_id": payload.get("sub"),
                    "email": payload.get("email") or payload.get("primary_email") or "",
                }
        elif _auth_dev_mode():
            return {"clerk_id": token, "email": f"{token}@dev.local"}

    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        studio_user = _lookup_api_key_user(api_key)
        if studio_user:
            return studio_user
        if api_key in _get_api_keys():
            return {"clerk_id": f"apikey:{api_key[:8]}", "email": "api@service.local"}

    if _auth_dev_mode() and os.getenv("AUTH_DEV_USER_ID"):
        return {
            "clerk_id": os.getenv("AUTH_DEV_USER_ID"),
            "email": os.getenv("AUTH_DEV_EMAIL", "dev@arcane-forge.local"),
        }

    return None


def require_user(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = resolve_auth_context()
        if not ctx or not ctx.get("clerk_id"):
            return jsonify({"error": "Authentication required"}), 401
        g.auth = ctx
        from services.users import get_or_create_user

        g.user = get_or_create_user(ctx["clerk_id"], ctx.get("email", ""))
        return func(*args, **kwargs)

    return wrapper


def optional_user(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = resolve_auth_context()
        g.auth = ctx
        g.user = None
        if ctx and ctx.get("clerk_id"):
            from services.users import get_or_create_user

            g.user = get_or_create_user(ctx["clerk_id"], ctx.get("email", ""))
        return func(*args, **kwargs)

    return wrapper


def require_api_key(func):
    """Legacy API key auth for backward compatibility."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        keys = _get_api_keys()
        if not keys:
            return require_user(func)(*args, **kwargs)
        provided = request.headers.get("X-API-Key", "")
        if provided not in keys:
            ctx = resolve_auth_context()
            if ctx:
                g.auth = ctx
                from services.users import get_or_create_user

                g.user = get_or_create_user(ctx["clerk_id"], ctx.get("email", ""))
                return func(*args, **kwargs)
            return jsonify({"error": "Invalid or missing API key"}), 401
        return func(*args, **kwargs)

    return wrapper
