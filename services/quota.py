"""Generation access — personal build; no credit or plan enforcement."""

from flask import jsonify


class QuotaError(Exception):
    def __init__(self, message: str, payload: dict):
        super().__init__(message)
        self.payload = payload


def credits_for_complexity(complexity: str) -> int:
    return 0


def plan_allows_complexity(plan: str, complexity: str) -> bool:
    return True


def plan_allows_character_sheets(plan: str) -> bool:
    return True


def check_and_deduct(user, complexity: str, job_id: str) -> int:
    """No-op: personal/portfolio build does not charge credits."""
    return 0


def refund_credits(user_id: str, amount: int, job_id: str, reason: str = "job_failed_refund") -> None:
    pass


def add_credits(user_id: str, amount: int, reason: str) -> None:
    pass


def reset_plan_credits(user_id: str, plan: str) -> None:
    pass


def quota_error_response(exc: QuotaError):
    return jsonify(exc.payload), 402
