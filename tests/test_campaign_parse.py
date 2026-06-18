"""Tests for campaign markdown parser."""

from examples.campaign_samples import get_sample_campaign
from services.campaign_parse import (
    count_sessions,
    extract_title,
    parse_campaign,
    slugify_title,
    word_count,
)


def test_extract_title():
    sample = get_sample_campaign("mediana", "en")
    assert extract_title(sample) == "The Shattered Crown of Valdris"


def test_slugify_title():
    assert slugify_title("The Shattered Crown!") == "the-shattered-crown"


def test_word_count_positive():
    sample = get_sample_campaign("mediana", "en")
    assert word_count(sample) > 100


def test_count_sessions_mediana():
    sample = get_sample_campaign("mediana", "en")
    assert count_sessions(sample) >= 3


def test_parse_campaign_sections():
    sample = get_sample_campaign("mediana", "en")
    parsed = parse_campaign(sample)
    assert parsed["title"] == "The Shattered Crown of Valdris"
    types = [s["type"] for s in parsed["sections"]]
    assert "overview" in types
    assert "session" in types
    assert "npcs" in types


def test_parse_session_objectives():
    sample = get_sample_campaign("mediana", "en")
    parsed = parse_campaign(sample)
    sessions = [s for s in parsed["sections"] if s["type"] == "session"]
    assert sessions
    assert sessions[0].get("objectives") or sessions[0].get("scenes")


def test_parse_npcs():
    sample = get_sample_campaign("mediana", "en")
    parsed = parse_campaign(sample)
    npc_section = next(s for s in parsed["sections"] if s["type"] == "npcs")
    assert len(npc_section["npcs"]) >= 2
