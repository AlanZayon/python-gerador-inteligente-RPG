"""Heuristic quality rubric for generated campaigns."""

from __future__ import annotations

import re
from typing import Any

from services.campaign_quality import count_sessions, word_count
from services.campaign_schema import canonical_complexity, spec_for

CATEGORIES = (
    "narrative",
    "gameplay",
    "npcs",
    "world",
    "content",
    "consistency",
    "gm_utility",
)
WEIGHTS = {
    "narrative": 1.2,
    "gameplay": 1.2,
    "npcs": 1.0,
    "world": 1.0,
    "content": 0.8,
    "consistency": 1.3,
    "gm_utility": 1.1,
}
OVERALL_THRESHOLD = 7.5
CATEGORY_FLOOR = 6.0

_GENERIC = (
    "ancient evil",
    "dark lord",
    "the tavern",
    "chosen one",
    "mysterious stranger",
    "forgotten ruins",
)
_CHOICE_RE = re.compile(
    r"\b(if the players|if they|alternatively|or they may|player choice|consequence)\b",
    re.I,
)
_CHECK_RE = re.compile(r"\b(DC\s*\d+|difficulty|3d6|roll|check|skill|resource)\b", re.I)
_NPC_FIELD_RE = re.compile(r"\b(want|goal|secret|role|motive)\b", re.I)
_PAREN_RE = re.compile(r"\s*\([^)]*\)")


def _clamp(score: float) -> float:
    return round(max(0.0, min(10.0, score)), 2)


def _item_name(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("name") or "").strip()
    return ""


def canonical_name(name: str) -> str:
    cleaned = _PAREN_RE.sub(" ", name or "")
    return re.sub(r"\s+", " ", cleaned).strip(" -–—")


def _name_in_text(name: str, lower: str) -> bool:
    raw = (name or "").strip()
    if not raw:
        return False
    if raw.lower() in lower:
        return True
    core = canonical_name(raw).lower()
    if core and core in lower:
        return True
    token = re.split(r"[\s(/,]", raw, maxsplit=1)[0].lower()
    if len(token) >= 4 and re.search(rf"\b{re.escape(token)}\b", lower):
        return True
    return False


def _state_names(state: dict[str, Any] | None) -> list[str]:
    if not state:
        return []
    names: list[str] = []
    for key in ("npcs", "factions", "locations", "fronts"):
        for item in state.get(key) or []:
            name = _item_name(item)
            if name:
                names.append(name)
    names.extend(t for t in (state.get("grounded_terms") or []) if str(t).strip())
    return names


def evaluate_rubric(
    markdown: str,
    *,
    complexity: str,
    state: dict[str, Any] | None = None,
    key_terms: list[str] | None = None,
) -> dict[str, Any]:
    spec = spec_for(complexity)
    text = markdown or ""
    lower = text.lower()
    wc = word_count(text)
    sessions = count_sessions(text)
    lo_s, _hi = spec["sessions"]
    names = _state_names(state)
    terms = [t for t in (key_terms or [])]
    if state:
        terms.extend(state.get("grounded_terms") or [])

    narrative = 6.0
    if re.search(r"\b(stake|conflict|premise|theme)\b", lower):
        narrative += 1.0
    if sessions >= lo_s:
        narrative += 1.0
    if re.search(r"\b(escalat|consequence|clock|front)\b", lower):
        narrative += 1.2
    if len(re.findall(r"^##\s+", text, re.M)) >= 6:
        narrative += 0.6

    gameplay = 5.0
    gameplay += min(3.0, len(_CHOICE_RE.findall(text)) * 0.5)
    if re.search(r"\b(stealth|social|negotiat|investigate|talk|sneak)\b", lower):
        gameplay += 1.2
    if re.search(r"\b(fail|if they refuse|if they fail)\b", lower):
        gameplay += 0.8

    npc_score = 4.5
    npc_score += min(3.0, len(re.findall(r"^###\s+", text, re.M)) * 0.35)
    npc_score += min(2.0, len(_NPC_FIELD_RE.findall(text)) * 0.15)
    if state and len(state.get("npcs") or []) >= spec["min_npcs"]:
        npc_score += 0.8

    world = 5.0
    if state:
        if len(state.get("factions") or []) >= spec["min_factions"]:
            world += 1.5
        if len(state.get("locations") or []) >= spec["min_locations"]:
            world += 1.2
        if len(state.get("fronts") or []) >= spec["min_fronts"]:
            world += 1.0
    grounded = sum(1 for t in terms if t.lower() in lower)
    if terms:
        world += min(2.0, 2.0 * grounded / max(1, min(6, len(terms))))

    content = 5.0
    ratio = wc / max(1, spec["word_target"])
    content += 2.5 if ratio >= 1 else (1.2 if ratio >= 0.7 else 0)
    content -= sum(1 for phrase in _GENERIC if phrase in lower) * 0.7
    if names:
        reused = sum(1 for n in names if _name_in_text(n, lower))
        content += min(2.0, 2.0 * reused / max(3, len(names)))

    consistency = 7.0
    if names:
        missing = [n for n in names[:12] if not _name_in_text(n, lower)]
        consistency -= min(4.0, len(missing) * 0.5)
    if sessions < lo_s:
        consistency -= 1.5

    gm_utility = 5.0
    gm_utility += min(2.5, len(_CHECK_RE.findall(text)) * 0.15)
    if re.search(r"\b(objective|gm note|if the players)\b", lower):
        gm_utility += 1.2
    if re.search(r"\b(treasure|reward|clue)\b", lower):
        gm_utility += 0.8
    if re.search(r"^###\s+", text, re.M):
        gm_utility += 0.6

    scores = {
        "narrative": _clamp(narrative),
        "gameplay": _clamp(gameplay),
        "npcs": _clamp(npc_score),
        "world": _clamp(world),
        "content": _clamp(content),
        "consistency": _clamp(consistency),
        "gm_utility": _clamp(gm_utility),
    }
    weight_sum = sum(WEIGHTS[c] for c in CATEGORIES)
    overall = _clamp(sum(scores[c] * WEIGHTS[c] for c in CATEGORIES) / weight_sum)
    issues = [f"{c} {scores[c]:.1f} < {CATEGORY_FLOOR}" for c in CATEGORIES if scores[c] < CATEGORY_FLOOR]
    if overall < OVERALL_THRESHOLD:
        issues.append(f"overall {overall:.2f} < {OVERALL_THRESHOLD}")
    weak = [c for c in CATEGORIES if scores[c] < OVERALL_THRESHOLD]
    passed = overall >= OVERALL_THRESHOLD and all(scores[c] >= CATEGORY_FLOOR for c in CATEGORIES)
    return {
        "scores": scores,
        "overall": overall,
        "passed": passed,
        "issues": issues,
        "weak_categories": weak,
        "complexity": canonical_complexity(complexity),
        "word_count": wc,
        "session_count": sessions,
        "threshold": OVERALL_THRESHOLD,
    }


def rubric_as_100(result: dict[str, Any]) -> int:
    return int(round(float(result.get("overall") or 0) * 10))


def format_rubric_report(result: dict[str, Any]) -> str:
    lines = [f"{cat.capitalize():<14} {result['scores'][cat]:.1f}/10" for cat in CATEGORIES]
    lines.append(f"{'Overall':<14} {result['overall']:.2f}/10")
    return "\n".join(lines)
