"""Tests for character sheet extraction and formatting."""

from services.sheet_extraction import (
    format_sheets_for_prompt,
    extract_character_names,
    parse_character_sheet,
)
from services.sheet_validation import (
    clamp_party_size,
    parse_use_character_sheets,
    validate_sheet_file_count,
    validate_sheets_json_size,
)


def test_clamp_party_size():
    assert clamp_party_size(0) == 1
    assert clamp_party_size(3) == 3
    assert clamp_party_size(10) == 5
    assert clamp_party_size("2") == 2


def test_parse_use_character_sheets():
    assert parse_use_character_sheets("true") is True
    assert parse_use_character_sheets("false") is False
    assert parse_use_character_sheets(None) is False


def test_validate_sheet_file_count():
    assert validate_sheet_file_count([], 3) == "Expected 3 character sheet PDF(s), got 0"
    assert validate_sheet_file_count([1, 2, 3], 3) is None
    assert validate_sheet_file_count([1, 2], 3) is not None


def test_format_sheets_for_prompt():
    sheets = [
        {"name": "Aldric", "class": "Fighter", "level": "5", "backstory": "A veteran."},
        {"name": "Mira", "class": "Wizard", "level": "4"},
    ]
    block = format_sheets_for_prompt(sheets)
    assert "PLAYER CHARACTERS" in block
    assert "Aldric" in block
    assert "Mira" in block


def test_extract_character_names():
    sheets = [
        {"name": "Aldric"},
        {"name": "Unknown"},
        {"name": "Player Character"},
        {"name": "Mira"},
    ]
    assert extract_character_names(sheets) == ["Aldric", "Mira"]


def test_parse_character_sheet_without_llm(monkeypatch):
    monkeypatch.setattr("services.sheet_extraction.is_configured", lambda: False)
    result = parse_character_sheet("Name: Thorin\nClass: Cleric", "dnd5e")
    assert result["name"] == "Player Character"
    assert "Thorin" in result["backstory"] or "Thorin" in result["raw_excerpt"]


def test_validate_sheets_json_size():
    small = [{"name": "A", "backstory": "x"}]
    assert validate_sheets_json_size(small) is None

    huge = [{"name": "X", "backstory": "y" * 60000}]
    assert validate_sheets_json_size(huge) is not None
