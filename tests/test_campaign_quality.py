"""Tests for campaign quality validation including book grounding."""

from services.campaign_quality import validate_campaign, word_count


def _long_campaign(extra: str = "") -> str:
    body = "word " * 2100
    return (
        "# Overview\nA dark hunt.\n\n## Session 1\nStart here.\n\n"
        "## Session 2\nContinue.\n\n## Session 3\nClimax.\n\n"
        "Important NPC: Mira\n" + body + extra
    )


def test_validate_campaign_min_words():
    short = "# Overview\nSession 1\n"
    passed, issues, score = validate_campaign(short, "mediana")
    assert not passed
    assert score < 100


def test_word_count():
    assert word_count("hello world test") == 3


def test_grounding_fails_without_book_terms():
    content = _long_campaign()
    passed, issues, score = validate_campaign(
        content, "mediana", key_terms=["Valdris", "Sahuagin", "Emberfall"]
    )
    assert not passed
    assert any("source book" in i for i in issues)


def test_grounding_passes_when_terms_present():
    content = _long_campaign(" Valdris and the Sahuagin of Emberfall.")
    passed, issues, score = validate_campaign(
        content, "mediana", key_terms=["Valdris", "Sahuagin", "Emberfall"]
    )
    assert passed, issues
    assert score >= 70
