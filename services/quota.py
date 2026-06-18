"""Credit quota enforcement."""

import os

from flask import jsonify

from database import SessionLocal
from models.entities import CreditTransaction, User
from services.users import PLAN_CREDITS

CREDIT_COSTS = {
    "simples": 1,
    "mediana": 2,
    "complexa": 4,
}

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


class QuotaError(Exception):
    def __init__(self, message: str, payload: dict):
        super().__init__(message)
        self.payload = payload


def credits_for_complexity(complexity: str) -> int:
    return CREDIT_COSTS.get(complexity, 2)


def plan_allows_complexity(plan: str, complexity: str) -> bool:
    if plan == "free" and complexity != "simples":
        return False
    return True


def check_and_deduct(user: User, complexity: str, job_id: str) -> int:
    cost = credits_for_complexity(complexity)
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user.id).with_for_update().first()
        if not u:
            raise QuotaError("User not found", {"error": "user_not_found"})

        if not plan_allows_complexity(u.plan, complexity):
            raise QuotaError(
                "Plan restriction",
                {
                    "error": "plan_restriction",
                    "message": "Free plan supports Simple campaigns only. Upgrade to Pro.",
                    "upgrade_url": f"{FRONTEND_URL}/pricing",
                },
            )

        if u.credits_balance < cost:
            raise QuotaError(
                "Insufficient credits",
                {
                    "error": "insufficient_credits",
                    "credits_required": cost,
                    "credits_available": u.credits_balance,
                    "upgrade_url": f"{FRONTEND_URL}/pricing",
                },
            )

        u.credits_balance -= cost
        db.add(
            CreditTransaction(
                user_id=u.id,
                amount=-cost,
                reason="campaign_generation",
                job_id=job_id,
            )
        )
        db.commit()
        return cost
    finally:
        db.close()


def refund_credits(user_id: str, amount: int, job_id: str, reason: str = "job_failed_refund") -> None:
    if amount <= 0:
        return
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            return
        u.credits_balance += amount
        db.add(CreditTransaction(user_id=user_id, amount=amount, reason=reason, job_id=job_id))
        db.commit()
    finally:
        db.close()


def add_credits(user_id: str, amount: int, reason: str) -> None:
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            return
        u.credits_balance += amount
        db.add(CreditTransaction(user_id=user_id, amount=amount, reason=reason, job_id=None))
        db.commit()
    finally:
        db.close()


def reset_plan_credits(user_id: str, plan: str) -> None:
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            return
        u.plan = plan
        u.credits_balance = PLAN_CREDITS.get(plan, 1)
        db.commit()
    finally:
        db.close()


def quota_error_response(exc: QuotaError):
    return jsonify(exc.payload), 402
