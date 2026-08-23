"""Lightweight RPG system detection from book text."""

import logging

from services.llm_client import complete, is_configured, model_lite

logger = logging.getLogger(__name__)

VALID_PRESETS = {"generic", "dnd5e", "pf2e", "coc", "gurps", "blood_honor", "fragged"}


def detect_system_heuristic(text_sample: str) -> str | None:
    """Fast lexical detection — used even when the LLM is unavailable."""
    lower = (text_sample or "").lower()
    if not lower.strip():
        return None
    if (
        "blood & honor" in lower
        or "blood and honor" in lower
        or "blood-honor" in lower
        or (
            "samurai" in lower
            and ("daimyo" in lower or "bushido" in lower or "clã" in lower or "clan" in lower)
        )
    ):
        return "blood_honor"
    if "gurps" in lower or "steve jackson" in lower or (
        "character points" in lower and "3d6" in lower
    ):
        return "gurps"
    if "fragged" in lower or "fragged empire" in lower or (
        "archon" in lower and ("corporation" in lower or "post-human" in lower)
    ):
        return "fragged"
    if "pathfinder" in lower or "three-action" in lower:
        return "pf2e"
    if "call of cthulhu" in lower or ("cthulhu" in lower and "sanity" in lower):
        return "coc"
    if "dungeons & dragons" in lower or "dungeons and dragons" in lower or "5th edition" in lower or "5e" in lower:
        return "dnd5e"
    return None


def detect_system_preset(text_sample: str) -> str | None:
    """Return preset id or None if uncertain."""
    heuristic = detect_system_heuristic(text_sample)
    if heuristic:
        return heuristic
    if not is_configured() or len(text_sample.strip()) < 200:
        return None
    sample = text_sample[:6000]
    ids = ", ".join(sorted(VALID_PRESETS))
    prompt = f"""Classify this RPG rulebook excerpt into ONE system id:
{ids}

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
    return None
