"""User provisioning and lookup."""

import os

from database import SessionLocal
from models.entities import User

PLAN_CREDITS = {
    "free": 1,
    "pro": 10,
    "studio": 40,
}


def _dev_user_overrides(clerk_id: str) -> tuple[str, int] | None:
    if os.getenv("AUTH_DEV_MODE", "false").lower() != "true":
        return None
    dev_id = os.getenv("AUTH_DEV_USER_ID", "")
    if not dev_id or clerk_id != dev_id:
        return None
    plan = os.getenv("AUTH_DEV_PLAN", "studio")
    credits_raw = os.getenv("AUTH_DEV_CREDITS", "")
    credits = int(credits_raw) if credits_raw else PLAN_CREDITS.get(plan, 40)
    return plan, credits


def get_or_create_user(clerk_id: str, email: str = "") -> User:
    db = SessionLocal()
    try:
        dev = _dev_user_overrides(clerk_id)
        user = db.query(User).filter(User.clerk_id == clerk_id).first()
        if user:
            changed = False
            if email and user.email != email:
                user.email = email
                changed = True
            if dev:
                plan, credits = dev
                if user.plan != plan:
                    user.plan = plan
                    changed = True
                if user.credits_balance < credits:
                    user.credits_balance = credits
                    changed = True
            if changed:
                db.commit()
                db.refresh(user)
            return user
        plan, credits = dev if dev else ("free", PLAN_CREDITS["free"])
        user = User(clerk_id=clerk_id, email=email, plan=plan, credits_balance=credits)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def get_user_by_id(user_id: str) -> User | None:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()
