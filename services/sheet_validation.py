"""Validation for character sheet uploads."""

import json

MAX_PARTY_SIZE = 5
MAX_SHEET_FILE_BYTES = 5 * 1024 * 1024
MAX_SHEETS_JSON_BYTES = 50 * 1024


def clamp_party_size(n: int | str | None) -> int:
    try:
        value = int(n or 1)
    except (TypeError, ValueError):
        value = 1
    return max(1, min(MAX_PARTY_SIZE, value))


def parse_use_character_sheets(value: str | None) -> bool:
    return str(value or "").lower() in ("true", "1", "yes")


def validate_sheet_file_count(sheet_files: list, party_size: int) -> str | None:
    if len(sheet_files) != party_size:
        return f"Expected {party_size} character sheet PDF(s), got {len(sheet_files)}"
    return None


def validate_sheet_file_size(file_storage) -> str | None:
    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_SHEET_FILE_BYTES:
        return f"Character sheet exceeds {MAX_SHEET_FILE_BYTES // (1024 * 1024)} MB limit"
    if size == 0:
        return "Character sheet file is empty"
    return None


def validate_sheets_json_size(sheets: list[dict]) -> str | None:
    encoded = json.dumps(sheets, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_SHEETS_JSON_BYTES:
        return "Character sheet data too large after extraction"
    return None
