"""Quality-first packing of retrieved chunks into a structured book context."""

from __future__ import annotations

import re

from services.rag.config import CONTEXT_BUDGETS
from services.rag.embeddings import count_tokens
from services.rag.retrieval import LANES, retrieve_coverage

JACCARD_DEDUP = 0.7
_STOP = {
    "page",
    "chapter",
    "section",
    "table",
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "setting",
    "excerpt",
    "excerpts",
    "mechanics",
    "locations",
    "factions",
    "creatures",
    "theme",
    "relevant",
    "tone",
    "overview",
    "session",
    "campanhas",
    "algumas",
    "outras",
    "assim",
    "mestre",
    "jogador",
    "jogadores",
    "quando",
    "onde",
    "como",
    "para",
    "pela",
    "pelo",
    "este",
    "esta",
    "esse",
    "essa",
    "isso",
    "aqui",
    "ability",
    "checks",
    "difficulty",
    "class",
}


def context_budget(complexity: str) -> tuple[int, int]:
    return CONTEXT_BUDGETS.get(complexity, CONTEXT_BUDGETS["mediana"])


def _jaccard(a: str, b: str) -> float:
    wa = {w for w in a.lower().split() if len(w) > 2}
    wb = {w for w in b.lower().split() if len(w) > 2}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _chunk_tokens(chunk: dict) -> int:
    stored = chunk.get("token_count")
    if isinstance(stored, int) and stored > 0:
        return stored
    return max(1, count_tokens(chunk.get("text") or ""))


def _dedup_lane(chunks: list[dict]) -> list[dict]:
    ordered = sorted(chunks, key=lambda c: float(c.get("score") or 0), reverse=True)
    kept: list[dict] = []
    for chunk in ordered:
        text = chunk.get("text") or ""
        if any(_jaccard(text, k.get("text") or "") >= JACCARD_DEDUP for k in kept):
            continue
        kept.append(chunk)
    return kept


def extract_key_terms(text: str, limit: int = 10) -> list[str]:
    words = re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕ][A-Za-záéíóúâêôãõç]{3,}\b", text or "")
    seen: set[str] = set()
    terms: list[str] = []
    for word in words:
        if word.lower() in _STOP or word in seen:
            continue
        seen.add(word)
        terms.append(word)
        if len(terms) >= limit:
            break
    return terms


def _format_lane(title: str, chunks: list[dict]) -> str:
    if not chunks:
        return f"## {title}\n(No excerpts in this band.)"
    parts = [f"## {title}"]
    for i, chunk in enumerate(chunks, start=1):
        score = chunk.get("score")
        score_str = f" (relevance {score:.2f})" if isinstance(score, float) and score else ""
        parts.append(f"### Excerpt {i}{score_str}\n{chunk['text']}")
    return "\n\n".join(parts)


def pack_lanes(
    lanes: dict[str, list[dict]],
    complexity: str = "mediana",
    floor: int | None = None,
    ceiling: int | None = None,
) -> dict:
    """Select unique verbatim excerpts with per-lane coverage and a token band."""
    default_floor, default_ceiling = context_budget(complexity)
    floor = default_floor if floor is None else floor
    ceiling = default_ceiling if ceiling is None else ceiling

    cleaned: dict[str, list[dict]] = {}
    used_ids: set = set()
    selected_texts: list[str] = []
    for lane in LANES:
        unique = []
        for chunk in _dedup_lane(lanes.get(lane) or []):
            cid = chunk.get("chunk_id")
            text = chunk.get("text") or ""
            if cid in used_ids:
                continue
            if any(_jaccard(text, prev) >= JACCARD_DEDUP for prev in selected_texts):
                continue
            used_ids.add(cid)
            selected_texts.append(text)
            unique.append(chunk)
        cleaned[lane] = unique

    selected: dict[str, list[dict]] = {lane: [] for lane in LANES}

    def total_tokens() -> int:
        return sum(_chunk_tokens(c) for cs in selected.values() for c in cs)

    # Floor coverage: at least one chunk per non-empty lane
    for lane in LANES:
        if cleaned[lane]:
            selected[lane].append(cleaned[lane][0])

    leftovers: list[tuple[str, dict]] = []
    for lane in LANES:
        for chunk in cleaned[lane][1:]:
            leftovers.append((lane, chunk))
    leftovers.sort(key=lambda item: float(item[1].get("score") or 0), reverse=True)

    for lane, chunk in leftovers:
        tokens = total_tokens()
        if tokens >= floor:
            break
        if tokens + _chunk_tokens(chunk) > ceiling:
            continue
        selected[lane].append(chunk)

    # Fill up toward ceiling without emptying a covered lane
    remaining = [
        (lane, chunk)
        for lane, chunk in leftovers
        if chunk not in selected[lane]
    ]
    remaining.sort(key=lambda item: float(item[1].get("score") or 0), reverse=True)
    for lane, chunk in remaining:
        next_total = total_tokens() + _chunk_tokens(chunk)
        if next_total > ceiling:
            continue
        selected[lane].append(chunk)

    # If still over ceiling, drop lowest-score extras but keep one per lane
    while total_tokens() > ceiling:
        extras = [
            (lane, chunk)
            for lane, chunks in selected.items()
            for chunk in chunks[1:]
        ]
        if not extras:
            break
        extras.sort(key=lambda item: float(item[1].get("score") or 0))
        lane, chunk = extras[0]
        selected[lane].remove(chunk)

    titles = {
        "setting": "Setting and tone",
        "mechanics": "Mechanics",
        "lore": "Locations, factions, creatures",
        "theme": "Theme-relevant excerpts",
    }
    sections = [_format_lane(titles[lane], selected[lane]) for lane in LANES]
    used_chunks = [c for lane in LANES for c in selected[lane]]
    book_context = "\n\n".join(sections)
    terms = extract_key_terms("\n".join(c.get("text") or "" for c in used_chunks))
    if terms:
        book_context += "\n\n## Key terms\n" + ", ".join(terms)

    setting_text = selected["setting"][0]["text"][:240] if selected["setting"] else ""
    return {
        "book_context": book_context,
        "key_terms": terms,
        "chunks_used": len(used_chunks),
        "token_count": total_tokens(),
        "setting": setting_text,
        "lanes_used": {lane: len(selected[lane]) for lane in LANES},
    }


def pack_campaign_context(
    book_id: str,
    *,
    theme: str = "",
    hook: str = "",
    system_preset: str | None = None,
    complexity: str = "mediana",
    top_k: int | None = None,
) -> dict:
    """Retrieve coverage lanes, widen k if below floor, then pack."""
    floor, _ceiling = context_budget(complexity)
    k = 8 if top_k is None else top_k
    lanes = retrieve_coverage(
        book_id,
        theme=theme,
        hook=hook,
        system_preset=system_preset,
        top_k=k,
    )
    packed = pack_lanes(lanes, complexity=complexity)
    if packed["token_count"] < floor:
        lanes = retrieve_coverage(
            book_id,
            theme=theme,
            hook=hook,
            system_preset=system_preset,
            top_k=max(k, 16),
        )
        packed = pack_lanes(lanes, complexity=complexity)
    return packed


# Alias used by older tests
extract_key_terms = extract_key_terms
