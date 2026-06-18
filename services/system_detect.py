"""Lightweight RPG system detection from book text."""

import json
import logging
import os

import google.generativeai as genai

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_CONFIGURED = bool(GEMINI_API_KEY and GEMINI_API_KEY != "sua_chave_aqui" and len(GEMINI_API_KEY) > 10)

VALID_PRESETS = {"generic", "dnd5e", "pf2e", "coc"}

if GEMINI_CONFIGURED:
    genai.configure(api_key=GEMINI_API_KEY)


def detect_system_preset(text_sample: str) -> str | None:
    """Return preset id or None if uncertain."""
    if not GEMINI_CONFIGURED or len(text_sample.strip()) < 200:
        return None
    sample = text_sample[:6000]
    prompt = f"""Classify this RPG rulebook excerpt into ONE system id:
generic, dnd5e, pf2e, coc

Return ONLY the id, nothing else.

Excerpt:
{sample}
"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
        response = model.generate_content(prompt)
        preset = (response.text or "").strip().lower().replace(" ", "")
        if preset in VALID_PRESETS:
            return preset
    except Exception as exc:
        logger.warning("System detect failed: %s", exc)

    lower = sample.lower()
    if "pathfinder" in lower or "three-action" in lower:
        return "pf2e"
    if "dungeons" in lower or "dragon" in lower or "5th edition" in lower:
        return "dnd5e"
    if "cthulhu" in lower or "sanity" in lower or "call of cthulhu" in lower:
        return "coc"
    return None
