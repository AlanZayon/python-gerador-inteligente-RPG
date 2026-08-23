"""Lightweight RPG system detection from book text."""

import logging

from services.llm_client import complete, is_configured, model_lite

logger = logging.getLogger(__name__)

VALID_PRESETS = {"generic", "dnd5e", "pf2e", "coc"}


def detect_system_preset(text_sample: str) -> str | None:
    """Return preset id or None if uncertain."""
    if not is_configured() or len(text_sample.strip()) < 200:
        return None
    sample = text_sample[:6000]
    prompt = f"""Classify this RPG rulebook excerpt into ONE system id:
generic, dnd5e, pf2e, coc

Return ONLY the id, nothing else.

Excerpt:
{sample}
"""
    try:
        preset = complete(prompt, model=model_lite(), temperature=0.1, max_tokens=32)
        preset = preset.strip().lower().replace(" ", "")
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
