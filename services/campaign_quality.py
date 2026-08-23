"""Campaign output quality validation."""

import re

MIN_WORDS = {
    "simples": 800,
    "mediana": 2000,
    "complexa": 4000,
}

REQUIRED_SECTIONS = [
    r"overview|visão geral|visao geral|resumo",
    r"session|sessão|sessao",
    r"npc",
]

SESSION_COUNTS = {
    "simples": (1, 2),
    "mediana": (3, 5),
    "complexa": (5, 20),
}


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def count_sessions(text: str) -> int:
    nums = [
        int(m)
        for m in re.findall(
            r"(?:session|sessão|sessao)\s*#?\s*(\d+)",
            text,
            re.IGNORECASE,
        )
    ]
    if nums:
        return max(nums)
    return len(
        re.findall(
            r"^#+\s*(?:session|sessão|sessao)\b",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
    )


def quality_requirements(complexity: str) -> str:
    min_w = MIN_WORDS.get(complexity, 2000)
    lo, _hi = SESSION_COUNTS.get(complexity, (3, 5))
    return (
        f"HARD REQUIREMENTS (rejected if missing):\n"
        f"- Write at least {min_w} words. Do not summarize. Write full playable detail.\n"
        f"- Include markdown heading `## Overview` (or `## Visão Geral` in Portuguese).\n"
        f"- Include at least {lo} sessions as headings: `## Session 1` ... `## Session {lo}` "
        f"(or `## Sessão 1` ...).\n"
        f"- Include a heading containing NPC (e.g. `## Important NPCs`).\n"
        f"- Each session needs objectives, encounters, NPCs, and treasures in multiple paragraphs."
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
    min_w = MIN_WORDS.get(complexity, 2000)
    if wc < min_w:
        issues.append(f"Word count {wc} below minimum {min_w}")

    lower = content.lower()
    for pattern in REQUIRED_SECTIONS:
        if not re.search(pattern, lower):
            issues.append(f"Missing section matching /{pattern}/")

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
