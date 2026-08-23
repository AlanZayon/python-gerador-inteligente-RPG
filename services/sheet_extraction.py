"""Extract and parse character sheet PDFs for campaign context."""

import json
import logging

import fitz

from services.llm_client import complete, is_configured, model_lite

logger = logging.getLogger(__name__)

MAX_PROMPT_CHARS = 8000


def extract_pdf_text(file_path: str) -> str:
    try:
        parts: list[str] = []
        with fitz.open(file_path) as doc:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                parts.append(page.get_text())
        return "\n".join(parts).strip()
    except Exception as exc:
        logger.error("Sheet text extraction failed: %s", exc)
        return ""


def _parse_json_response(text: str) -> dict:
    text = (text or "").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def parse_character_sheet(text: str, system_preset: str | None = None) -> dict:
    """Parse extracted sheet text into structured fields."""
    excerpt = (text or "")[:12000]
    if not excerpt.strip():
        return {
            "name": "Unknown",
            "class": "",
            "level": "",
            "abilities": "",
            "equipment": "",
            "backstory": "",
            "raw_excerpt": "",
        }

    if not is_configured():
        return {
            "name": "Player Character",
            "class": "",
            "level": "",
            "abilities": "",
            "equipment": "",
            "backstory": excerpt[:2000],
            "raw_excerpt": excerpt[:3000],
        }

    prompt = f"""Extract character sheet data from this RPG character sheet text.
System preset: {system_preset or "generic"}

Return ONLY valid JSON with keys:
name, class, level, abilities, equipment, backstory, raw_excerpt

Use empty strings for missing fields. raw_excerpt: short summary of key stats (max 500 chars).

SHEET TEXT:
{excerpt}
"""
    try:
        text = complete(prompt, model=model_lite(), temperature=0.2)
        parsed = _parse_json_response(text)
        if parsed.get("name"):
            parsed.setdefault("raw_excerpt", excerpt[:500])
            return parsed
    except Exception as exc:
        logger.warning("9router sheet parse failed: %s", exc)

    return {
        "name": "Player Character",
        "class": "",
        "level": "",
        "abilities": "",
        "equipment": "",
        "backstory": excerpt[:2000],
        "raw_excerpt": excerpt[:3000],
    }


def format_sheets_for_prompt(sheets: list[dict]) -> str:
    """Format player characters block for campaign prompts."""
    if not sheets:
        return ""

    lines = ["## PLAYER CHARACTERS", ""]
    for i, sheet in enumerate(sheets, 1):
        name = sheet.get("name") or f"Player {i}"
        lines.append(f"### {name}")
        for key in ("class", "level", "abilities", "equipment", "backstory"):
            val = sheet.get(key)
            if val:
                label = key.replace("_", " ").title()
                lines.append(f"- **{label}**: {val}")
        excerpt = sheet.get("raw_excerpt")
        if excerpt and not sheet.get("backstory"):
            lines.append(f"- **Notes**: {excerpt}")
        lines.append("")

    block = "\n".join(lines)
    if len(block) > MAX_PROMPT_CHARS:
        return block[:MAX_PROMPT_CHARS] + "\n...(truncated)"
    return block


def extract_character_names(sheets: list[dict]) -> list[str]:
    names = []
    for sheet in sheets:
        name = (sheet.get("name") or "").strip()
        if name and name.lower() not in ("unknown", "player character"):
            names.append(name)
    return names
