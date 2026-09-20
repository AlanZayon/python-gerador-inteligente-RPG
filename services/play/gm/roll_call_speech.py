"""Spoken Roll Call for the table — not stage directions."""

from __future__ import annotations

import re

# One nested paren level, e.g. Sabedoria (Percepção) inside a wait aside.
_NESTED = r"(?:[^()]|\([^()]*\))*"
_WAIT_KW = (
    r"(?:aguardando(?:\s+a)?\s+rolagem|esperando\s+(?:o\s+)?jogador|"
    r"waiting\s+for(?:\s+(?:the\s+)?player)?(?:\s+to\s+roll)?|"
    r"the\s+table\s+waits\s+for\s+(?:the\s+)?(?:player|roll))"
)

_WAIT_ITALIC_PAREN = re.compile(
    rf"\*+\s*\({_NESTED}{_WAIT_KW}{_NESTED}\)\.?\s*\*+",
    re.I,
)
_WAIT_PAREN = re.compile(
    rf"\({_NESTED}{_WAIT_KW}{_NESTED}\)",
    re.I,
)
_WAIT_ITALIC = re.compile(
    rf"\*+[^*]*{_WAIT_KW}[^*]*\*+",
    re.I,
)
_WAIT_SENTENCE = re.compile(
    rf"(?:^|[.!?]\s+){_WAIT_KW}[^.!?]*[.!]?",
    re.I,
)
_ROLL_CUE = re.compile(
    r"\b(?:teste|testa|rola(?:r|gem)?|roll(?:ing)?|check|fa[cç]a\s+um)\b",
    re.I,
)
_PT_MARK = re.compile(
    r"[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]|"
    r"\b(?:faça|teste|rolagem|aguardando|jogador|você|sabedoria|"
    r"percep[cç][aã]o|atletismo|destreza|força|carisma)\b",
    re.I,
)


def has_wait_meta(text: str) -> bool:
    raw = text or ""
    return bool(
        _WAIT_ITALIC_PAREN.search(raw)
        or _WAIT_PAREN.search(raw)
        or _WAIT_ITALIC.search(raw)
        or _WAIT_SENTENCE.search(raw)
    )


def scrub_roll_wait_meta(text: str) -> str:
    """Drop 'waiting for the player to roll' asides so TTS never speaks them."""
    cleaned = text or ""
    cleaned = _WAIT_ITALIC_PAREN.sub("", cleaned)
    cleaned = _WAIT_PAREN.sub("", cleaned)
    cleaned = _WAIT_ITALIC.sub("", cleaned)
    cleaned = _WAIT_SENTENCE.sub(".", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned.strip(" \t\n.")


def infer_table_language(
    text: str,
    pending: dict | None = None,
    fallback: str = "en",
) -> str:
    blob = f"{text or ''} {((pending or {}).get('skill') or '')}"
    if _PT_MARK.search(blob):
        return "pt"
    lang = (fallback or "en").lower()
    return "pt" if lang.startswith("pt") else "en"


def format_spoken_roll_call(
    pending: dict | None,
    *,
    character_name: str = "",
    language: str = "en",
) -> str:
    pending = pending if isinstance(pending, dict) else {}
    skill = (pending.get("skill") or "check").strip() or "check"
    notation = (pending.get("notation") or "").strip()
    dc = pending.get("dc")
    who = (character_name or "").strip()
    lang = (language or "en").lower()
    alts = pending.get("alternatives") if isinstance(pending.get("alternatives"), list) else []
    if len(alts) > 1:
        names = [(a.get("skill") or "check").strip() or "check" for a in alts]
        if lang.startswith("pt"):
            who = who or "Você"
            joined = " ou ".join(names)
            dc_bit = f", CD {dc}" if dc is not None and str(dc) != "" else ""
            return f"{who}, escolha um teste: {joined}{dc_bit}."
        who = who or "You"
        joined = " or ".join(names)
        dc_bit = f" against DC {dc}" if dc is not None and str(dc) != "" else ""
        return f"{who}, choose a check: {joined}{dc_bit}."
    if lang.startswith("pt"):
        who = who or "Você"
        dice = f", {notation}" if notation else ""
        dc_bit = f", CD {dc}" if dc is not None and str(dc) != "" else ""
        return f"{who}, faça um teste de {skill}{dice}{dc_bit}."
    who = who or "You"
    dice = f" ({notation})" if notation else ""
    dc_bit = f" against DC {dc}" if dc is not None and str(dc) != "" else ""
    return f"{who}, make a {skill} check{dice}{dc_bit}."


def narration_asks_for_roll(text: str, pending: dict | None) -> bool:
    lower = (text or "").lower()
    if not lower:
        return False
    if _ROLL_CUE.search(lower):
        return True
    skill = ((pending or {}).get("skill") or "").lower().strip()
    if skill and skill in lower:
        return True
    first = skill.split("(")[0].strip() if skill else ""
    return bool(first and first in lower)


def ensure_spoken_roll_call(
    narration: str,
    pending: dict | None,
    *,
    character_name: str = "",
    language: str = "en",
) -> str:
    """Keep scene prose, strip wait-meta, and speak the Roll Call as the GM."""
    if not isinstance(pending, dict) or not pending:
        return scrub_roll_wait_meta(narration) or (narration or "").strip()
    cleaned = scrub_roll_wait_meta(narration)
    lang = infer_table_language(narration, pending, fallback=language)
    call = format_spoken_roll_call(
        pending, character_name=character_name, language=lang
    )
    if narration_asks_for_roll(cleaned, pending):
        return cleaned
    if cleaned:
        return f"{cleaned.rstrip('.')}. {call}"
    return call
