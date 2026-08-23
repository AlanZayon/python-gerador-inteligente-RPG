"""Tests for campaign quality validation including book grounding."""

from services.campaign_quality import (
    heal_missing_sections,
    is_collapsed_draft,
    validate_campaign,
    word_count,
)


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


def test_pnj_heading_satisfies_npc_requirement():
    content = _long_campaign().replace("Important NPC: Mira", "## PNJs Importantes\nMira")
    passed, issues, _score = validate_campaign(content, "mediana")
    assert passed, issues


def test_heal_inserts_missing_npc_heading():
    body = "# Title\n\n## Overview\nA hunt.\n\n## Session 1\nBegin.\n\n" + ("word " * 900)
    passed, issues, _score = validate_campaign(body, "simples")
    assert not passed
    assert any("npc" in i for i in issues)
    healed = heal_missing_sections(body, issues, "en")
    passed2, issues2, _score2 = validate_campaign(healed, "simples")
    assert passed2, issues2
    assert "## Important NPCs" in healed


def test_collapsed_retry_is_detected():
    long_draft = "word " * 2000
    stub = "short summary of the campaign " * 10
    assert is_collapsed_draft(long_draft, stub)
    assert not is_collapsed_draft(stub, long_draft)


def _localized_simple(overview: str, session: str, npc: str) -> str:
    return (
        f"## {overview}\nA hunt.\n\n## {session} 1\nBegin.\n\n## {npc}\nMira.\n\n"
        + ("word " * 900)
    )


def test_spanish_headings_pass_quality():
    passed, issues, _score = validate_campaign(
        _localized_simple("Visión general", "Sesión", "PNJs importantes"),
        "simples",
    )
    assert passed, issues


def test_french_headings_pass_quality():
    passed, issues, _score = validate_campaign(
        _localized_simple("Aperçu", "Session", "PNJ importants"),
        "simples",
    )
    assert passed, issues


def test_german_headings_pass_quality():
    passed, issues, _score = validate_campaign(
        _localized_simple("Überblick", "Sitzung", "Wichtige NSCs"),
        "simples",
    )
    assert passed, issues


def test_japanese_headings_pass_quality():
    passed, issues, _score = validate_campaign(
        _localized_simple("概要", "セッション", "重要NPC"),
        "simples",
    )
    assert passed, issues


def test_russian_headings_pass_quality():
    passed, issues, _score = validate_campaign(
        _localized_simple("Обзор", "Сессия", "Важные NPC"),
        "simples",
    )
    assert passed, issues


def test_heal_uses_target_language_labels():
    body = "# Title\n\n## Überblick\nA hunt.\n\n## Sitzung 1\nBegin.\n\n" + ("word " * 900)
    passed, issues, _score = validate_campaign(body, "simples")
    assert not passed
    healed = heal_missing_sections(body, issues, "de")
    assert "Wichtige NSCs" in healed
    passed2, issues2, _score2 = validate_campaign(healed, "simples")
    assert passed2, issues2
