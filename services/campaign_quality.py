"""Campaign output quality validation."""

import re

MIN_WORDS = {
    "simples": 800,
    "mediana": 2000,
    "complexa": 4000,
}

REQUIRED_SECTIONS = [
    r"overview|visão geral|visao geral",
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
    matches = re.findall(
        r"(?:session|sessão|sessao)\s*#?\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    if matches:
        return max(int(m) for m in matches)
    return len(re.findall(r"##\s*(?:Session|Sessão|Sessao)\s*\d", text, re.IGNORECASE))


def validate_campaign(content: str, complexity: str) -> tuple[bool, list[str], int]:
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

    score = 100
    score -= max(0, (min_w - wc) // 50) * 5
    score -= len(issues) * 15
    score = max(0, min(100, score))

    return len(issues) == 0, issues, score
