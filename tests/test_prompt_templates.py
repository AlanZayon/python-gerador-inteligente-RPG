"""Tests for campaign prompt templates with character sheets."""

from services.prompt_templates import build_campaign_prompt


def test_prompt_includes_player_characters_block():
    sheets_block = "## PLAYER CHARACTERS\n\n### Aldric\n- **Class**: Fighter"
    prompt = build_campaign_prompt(
        book_bible={"title": "Test Book"},
        target_language="en",
        complexity="mediana",
        guidelines="- 3 sessions",
        system_preset="dnd5e",
        character_sheets=sheets_block,
    )
    assert "PLAYER CHARACTERS" in prompt
    assert "Aldric" in prompt
    assert "CHARACTER ARCHETYPES" not in prompt
    assert "personalized plot threads" in prompt.lower()


def test_prompt_without_sheets_keeps_archetypes():
    prompt = build_campaign_prompt(
        book_bible={"title": "Test Book"},
        target_language="en",
        complexity="simples",
        guidelines="- 1 session",
        system_preset="generic",
    )
    assert "CHARACTER ARCHETYPES" in prompt
