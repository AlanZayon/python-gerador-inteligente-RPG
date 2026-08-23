"""Campaign output quality validation."""

import re

from services.campaign_i18n import (
    NPC_RE,
    OVERVIEW_RE,
    count_sessions as i18n_count_sessions,
    markdown_schema,
    section_label,
)

MIN_WORDS = {
    "simples": 800,
    "mediana": 2000,
    "complexa": 4000,
}

_COMPLEXITY_ALIASES = {
    "simple": "simples",
    "medium": "mediana",
    "complex": "complexa",
    "complexo": "complexa",
}

REQUIRED_SECTIONS = [
    (OVERVIEW_RE, "overview"),
    (NPC_RE, "npc"),
]

SESSION_COUNTS = {
    "simples": (1, 2),
    "mediana": (3, 5),
    "complexa": (5, 20),
}


def canonical_complexity(complexity: str) -> str:
    key = (complexity or "mediana").lower().strip()
    return _COMPLEXITY_ALIASES.get(key, key)


def word_count(text: str) -> int:
    tokens = re.findall(r"\w+", text or "", flags=re.UNICODE)
    cjk = re.findall(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text or "")
    if len(cjk) >= 80:
        return max(len(tokens), len(cjk) // 2)
    return len(tokens)


def count_sessions(text: str) -> int:
    return i18n_count_sessions(text)


def quality_requirements(complexity: str, language: str = "en") -> str:
    min_w = MIN_WORDS.get(canonical_complexity(complexity), 2000)
    lo, _hi = SESSION_COUNTS.get(canonical_complexity(complexity), (3, 5))
    overview = section_label("overview", language)
    session = section_label("session", language)
    npcs = section_label("npcs", language)
    return (
        f"HARD REQUIREMENTS (rejected if missing):\n"
        f"- Write at least {min_w} words. Do not summarize. Write full playable detail.\n"
        f"- Include markdown heading `## {overview}`.\n"
        f"- Include at least {lo} sessions as headings: `## {session} 1` ... `## {session} {lo}`.\n"
        f"- Include a heading for NPCs: `## {npcs}`.\n"
        f"- Each session needs objectives, encounters, NPCs, and treasures in multiple paragraphs.\n"
        f"\n{markdown_schema(language)}"
    )


def validate_campaign(
    content: str,
    complexity: str,
    character_names: list[str] | None = None,
    key_terms: list[str] | None = None,
) -> tuple[bool, list[str], int]:
    """Return (passed, issues, quality_score 0-100)."""
    issues: list[str] = []
    wc = word_count(content)
    complexity = canonical_complexity(complexity)
    min_w = MIN_WORDS.get(complexity, 2000)
    if wc < min_w:
        issues.append(f"Word count {wc} below minimum {min_w}")

    lower = content.lower()
    for pattern, name in REQUIRED_SECTIONS:
        if not pattern.search(content or ""):
            issues.append(f"Missing {name} section")

    sessions = count_sessions(content)
    lo, hi = SESSION_COUNTS.get(complexity, (2, 6))
    if sessions < lo:
        issues.append(f"Expected at least {lo} sessions, found {sessions}")

    terms = [t for t in (key_terms or []) if t and len(t) > 3]
    grounding_hits = 0
    if terms:
        grounding_hits = sum(1 for t in terms if t.lower() in lower)
        required = max(1, (len(terms) + 2) // 3)
        if grounding_hits < required:
            issues.append(
                "Campaign does not use enough terms from the source book: "
                + ", ".join(terms[:10])
            )

    score = 100
    score -= max(0, (min_w - wc) // 50) * 5
    score -= len(issues) * 15

    if character_names:
        missing = [n for n in character_names if n.lower() not in lower]
        if missing and len(missing) < len(character_names):
            score -= min(10, len(missing) * 3)

    if terms:
        score -= max(0, (len(terms) - grounding_hits) * 2)

    score = max(0, min(100, score))

    return len(issues) == 0, issues, score


def heal_missing_sections(content: str, issues: list[str], language: str = "en") -> str:
    """Insert canonical headings when the draft is complete but mislabeled."""
    healed = content or ""
    blob = " ".join(issues).lower()

    if "npc" in blob and not NPC_RE.search(healed):
        healed = healed.rstrip() + f"\n\n## {section_label('npcs', language)}\n"

    if "overview" in blob and not OVERVIEW_RE.search(healed):
        heading = f"## {section_label('overview', language)}"
        if re.search(r"^# .+$", healed, re.MULTILINE):
            healed = re.sub(
                r"^(# .+)$",
                rf"\1\n\n{heading}\n",
                healed,
                count=1,
                flags=re.MULTILINE,
            )
        else:
            healed = f"{heading}\n\n{healed}"

    if "session" in blob and count_sessions(healed) < 1:
        healed = (
            healed.rstrip() + f"\n\n## {section_label('session', language)} 1\n"
        )

    return healed


def is_collapsed_draft(previous: str, candidate: str) -> bool:
    """True when a retry threw away a long playable draft."""
    prev_w = word_count(previous)
    new_w = word_count(candidate)
    return prev_w >= 600 and new_w < max(400, int(prev_w * 0.5))


def draft_rank(content: str, issues: list[str], score: int) -> tuple[int, int, int]:
    return (-len(issues), word_count(content), score)
