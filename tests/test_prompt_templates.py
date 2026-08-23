"""Tests for campaign prompt templates with character sheets."""

from services.prompt_templates import build_campaign_prompt, build_expand_retry_prompt


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


def test_prompt_uses_book_context_and_grounding_instruction():
    prompt = build_campaign_prompt(
        book_context="The city of Valdris drowns beneath the Sahuagin Court.",
        target_language="en",
        complexity="mediana",
        guidelines="- 3 sessions",
        system_preset="generic",
        theme="rising tide",
    )
    assert "BOOK CONTEXT" in prompt
    assert "Valdris" in prompt
    assert "generic fantasy" in prompt.lower()
    assert "rising tide" in prompt
    assert "2000" in prompt
    assert "## Overview" in prompt
    assert "## Session 3" in prompt


def test_retry_prompt_demands_full_campaign_rewrite():
    prompt = build_expand_retry_prompt(
        content="# Short draft",
        issues=["Word count 302 below minimum 2000"],
        target_language="en",
        key_terms=["Valdris"],
        complexity="mediana",
    )
    assert "COMPLETE play-ready RPG campaign" in prompt
    assert "Do not return a summary" in prompt
    assert "2000" in prompt
    assert "Valdris" in prompt
    assert "HARD REQUIREMENTS" in prompt
