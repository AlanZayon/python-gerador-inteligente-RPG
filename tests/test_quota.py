"""Generation access — no credit enforcement in personal build."""

from services.quota import (
    check_and_deduct,
    credits_for_complexity,
    plan_allows_character_sheets,
    plan_allows_complexity,
    refund_credits,
)


def test_check_and_deduct_returns_zero():
    assert check_and_deduct(object(), "complexa", "job-1") == 0


def test_credits_for_complexity_is_zero():
    assert credits_for_complexity("simples") == 0
    assert credits_for_complexity("complexa") == 0


def test_all_complexities_allowed():
    assert plan_allows_complexity("free", "simples") is True
    assert plan_allows_complexity("free", "mediana") is True
    assert plan_allows_complexity("free", "complexa") is True


def test_character_sheets_allowed_for_all_plans():
    assert plan_allows_character_sheets("free") is True
    assert plan_allows_character_sheets("pro") is True


def test_refund_credits_is_no_op():
    refund_credits("user-id", 5, "job-2")
