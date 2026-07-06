"""Tests for RAG prompt assembly and generator (mock LLM)."""

from unittest.mock import patch

import numpy as np
import pytest

from services.rag.generator import generate_campaign
from services.rag.prompt_builder import build_rag_prompt


def test_build_rag_prompt_contains_required_sections():
    chunks = [
        {"text": "The city of Valdris lies beneath the waves.", "score": 0.9},
        {"text": "Sahuagin patrol the coral reefs at night.", "score": 0.8},
    ]
    prompt = build_rag_prompt(
        chunks=chunks,
        theme="dark fantasy",
        hook="Submerged city rises",
        target_language="pt",
        system_preset="generic",
        tone="grim",
        party_level="3-5",
        character_sheets=["Name: Mira, Class: Rogue"],
    )

    assert "Valdris" in prompt
    assert "dark fantasy" in prompt
    assert "Submerged city rises" in prompt
    assert "Mira" in prompt
    assert "OVERVIEW" in prompt
    assert "Language: pt" in prompt
    assert "Excerpt 1" in prompt


@patch("services.rag.generator.retrieve")
@patch("services.rag.generator.index_exists", return_value=True)
def test_generate_campaign_with_mock_llm(mock_exists, mock_retrieve):
    mock_retrieve.return_value = [
        {"text": "Horror setting with undead.", "score": 0.85},
    ]

    def fake_llm(prompt: str) -> str:
        assert "Horror setting" in prompt
        return "# Test Campaign\n\nOverview of the adventure."

    result = generate_campaign(
        book_id="test-book",
        theme="horror",
        hook="Graveyard at midnight",
        target_language="en",
        llm_fn=fake_llm,
    )

    assert result["generation_source"] == "llama"
    assert result["book_id"] == "test-book"
    assert result["chunks_used"] == 1
    assert "Test Campaign" in result["campaign"]


@patch("services.rag.generator.index_exists", return_value=False)
def test_generate_campaign_missing_index(mock_exists):
    with pytest.raises(Exception):
        generate_campaign(book_id="missing", theme="horror")
