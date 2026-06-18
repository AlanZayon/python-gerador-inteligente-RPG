"""Parse campaign markdown into structured sections for UI and PDF."""

import re
from typing import Any

SESSION_HEADING = re.compile(
    r"^(?:session|sessão|sessao)\s*#?\s*(\d+)",
    re.IGNORECASE,
)
OVERVIEW_HEADING = re.compile(
    r"overview|visão geral|visao geral|sinopse",
    re.IGNORECASE,
)
HOOK_HEADING = re.compile(
    r"starting hook|gancho|hook inicial|opening hook",
    re.IGNORECASE,
)
NPC_HEADING = re.compile(
    r"important npcs?|npcs?|personagens|pnjs?",
    re.IGNORECASE,
)
REWARDS_HEADING = re.compile(
    r"rewards?|recompensas?|treasure|tesouro",
    re.IGNORECASE,
)
INSPIRED_HEADING = re.compile(
    r"inspired by|inspirado",
    re.IGNORECASE,
)
NPC_LINE = re.compile(r"^[-*]\s+\*\*(.+?)\*\*[:\s—–-]+(.+)$", re.MULTILINE)
OBJECTIVES = re.compile(
    r"\*\*(?:objectives?|objetivos?)[:\s]*\*\*[:\s]*(.+?)(?=\n\*\*|\n##|\Z)",
    re.IGNORECASE | re.DOTALL,
)
SCENE = re.compile(
    r"\*\*(?:scene|scena|cena)\s*([A-Z0-9])?[:\s—–-]*\*\*[:\s—–-]*(.+?)(?=\n\*\*(?:scene|scena|cena|combat|puzzle|boss)|\n##|\Z)",
    re.IGNORECASE | re.DOTALL,
)
COMBAT = re.compile(
    r"\*\*(?:combat|combate|boss)[:\s]*\*\*[:\s]*(.+?)(?=\n\*\*|\n##|\Z)",
    re.IGNORECASE | re.DOTALL,
)
PUZZLE = re.compile(
    r"\*\*(?:puzzle|quebra-cabeça|enigma)[:\s]*\*\*[:\s]*(.+?)(?=\n\*\*|\n##|\Z)",
    re.IGNORECASE | re.DOTALL,
)


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


def slugify_title(title: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:max_len] or "campaign"


def extract_title(content: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else "Campaign"


def _classify_heading(heading: str) -> str:
    if SESSION_HEADING.search(heading):
        return "session"
    if OVERVIEW_HEADING.search(heading):
        return "overview"
    if HOOK_HEADING.search(heading):
        return "hook"
    if NPC_HEADING.search(heading):
        return "npcs"
    if REWARDS_HEADING.search(heading):
        return "rewards"
    if INSPIRED_HEADING.search(heading):
        return "inspired"
    return "generic"


def _parse_session_body(body: str) -> dict[str, Any]:
    objectives_match = OBJECTIVES.search(body)
    scenes = [
        {"label": (m.group(1) or "").strip(), "text": m.group(2).strip()}
        for m in SCENE.finditer(body)
    ]
    combat_match = COMBAT.search(body)
    puzzle_match = PUZZLE.search(body)
    tags: list[str] = []
    if scenes or re.search(r"social|investigation|talk", body, re.I):
        tags.append("Social")
    if combat_match:
        tags.append("Combat")
    if puzzle_match:
        tags.append("Puzzle")
    return {
        "objectives": objectives_match.group(1).strip() if objectives_match else "",
        "scenes": scenes,
        "combat": combat_match.group(1).strip() if combat_match else "",
        "puzzle": puzzle_match.group(1).strip() if puzzle_match else "",
        "tags": tags,
    }


def _parse_npcs(body: str) -> list[dict[str, str]]:
    npcs = []
    for match in NPC_LINE.finditer(body):
        npcs.append({"name": match.group(1).strip(), "description": match.group(2).strip()})
    if not npcs:
        for line in body.splitlines():
            line = line.strip()
            if line.startswith(("-", "*")):
                text = re.sub(r"^[-*]\s+", "", line)
                if "**" in text:
                    parts = re.split(r"\*\*", text)
                    if len(parts) >= 3:
                        npcs.append({"name": parts[1].strip(), "description": parts[2].strip(": —–-")})
                elif ":" in text:
                    name, _, desc = text.partition(":")
                    npcs.append({"name": name.strip(), "description": desc.strip()})
    return npcs


def parse_campaign(content: str) -> dict[str, Any]:
    """Return structured campaign data from markdown."""
    title = extract_title(content)
    sections_raw = re.split(r"^##\s+(.+)$", content, flags=re.MULTILINE)
    preamble = sections_raw[0].strip() if sections_raw else ""
    sections: list[dict[str, Any]] = []

    i = 1
    while i < len(sections_raw) - 1:
        heading = sections_raw[i].strip()
        body = sections_raw[i + 1].strip()
        section_type = _classify_heading(heading)
        section: dict[str, Any] = {
            "type": section_type,
            "heading": heading,
            "content": body,
            "id": f"sec-{len(sections)}",
        }
        if section_type == "session":
            num_match = SESSION_HEADING.search(heading)
            section["number"] = int(num_match.group(1)) if num_match else len(sections) + 1
            section.update(_parse_session_body(body))
        elif section_type == "npcs":
            section["npcs"] = _parse_npcs(body)
        sections.append(section)
        i += 2

    wc = word_count(content)
    sc = count_sessions(content)
    return {
        "title": title,
        "preamble": preamble,
        "sections": sections,
        "stats": {
            "wordCount": wc,
            "sessionCount": sc,
            "estimatedReadMinutes": max(1, wc // 200),
        },
    }


def build_job_meta(job, content: str, redis_result: dict | None = None) -> dict[str, Any]:
    """Build meta dict for /content endpoint."""
    parsed = parse_campaign(content)
    result = redis_result or {}
    book_signals = result.get("book_signals")
    if isinstance(book_signals, str):
        try:
            import json

            book_signals = json.loads(book_signals)
        except Exception:
            book_signals = []
    quality = result.get("quality_score")
    if quality is not None:
        try:
            quality = int(float(quality))
        except (TypeError, ValueError):
            quality = None
    return {
        "title": parsed["title"],
        "complexity": job.complexity,
        "language": job.language,
        "filename": job.filename,
        "word_count": parsed["stats"]["wordCount"],
        "session_count": parsed["stats"]["sessionCount"],
        "quality_score": quality,
        "book_signals": book_signals if isinstance(book_signals, list) else [],
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
