"""Semantic retrieval — multi-query coverage, no LLM classification."""

from services.rag.config import RAG_TOP_K
from services.rag.embeddings import embed_texts
from services.rag.faiss_store import opening_chunks, search

LANES = ("setting", "mechanics", "lore", "theme")

_MECHANICS_QUERIES = {
    "dnd5e": (
        "Dungeons and Dragons 5e combat spells ability checks rest hit points "
        "armor class saving throws conditions"
    ),
    "pf2e": (
        "Pathfinder 2e three-action economy proficiency skills spells feats "
        "level-based DCs Recall Knowledge"
    ),
    "coc": (
        "Call of Cthulhu sanity investigation skills percentiles clues horror "
        "occupation"
    ),
    "generic": "RPG game mechanics combat skills magic rules checks difficulty",
}

_SETTING_QUERY = (
    "campaign setting world tone atmosphere geography culture history "
    "thematic overview of the world"
)
_LORE_QUERY = (
    "named locations factions creatures NPCs organizations landmarks "
    "settlements enemies"
)


def build_query(theme: str, hook: str = "") -> str:
    """
    Build a retrieval query from campaign theme and optional hook.

    Fixed template — no LLM query expansion (keeps cost and complexity low).
    """
    parts = [f"RPG campaign setting and rules related to theme: {theme}"]
    if hook:
        parts.append(f"Campaign hook: {hook}")
    return ". ".join(parts)


def _lane_queries(
    theme: str,
    hook: str = "",
    system_preset: str | None = None,
) -> dict[str, str]:
    preset = system_preset or "generic"
    theme_q = build_query(theme or "adventure", hook)
    return {
        "setting": _SETTING_QUERY,
        "mechanics": _MECHANICS_QUERIES.get(preset, _MECHANICS_QUERIES["generic"]),
        "lore": _LORE_QUERY if not theme else f"{_LORE_QUERY}. Theme: {theme}",
        "theme": theme_q,
    }


def retrieve(
    book_id: str,
    theme: str,
    hook: str = "",
    top_k: int | None = None,
) -> list[dict]:
    """Embed query and return top-k chunks from FAISS."""
    k = top_k if top_k is not None else RAG_TOP_K
    query = build_query(theme, hook)
    query_vec = embed_texts([query])[0]
    return search(book_id, query_vec, k)


def retrieve_coverage(
    book_id: str,
    theme: str = "",
    hook: str = "",
    system_preset: str | None = None,
    top_k: int | None = None,
) -> dict[str, list[dict]]:
    """Retrieve chunks for setting, mechanics, lore, and theme lanes."""
    k = top_k if top_k is not None else RAG_TOP_K
    queries = _lane_queries(theme, hook, system_preset)
    texts = [queries[lane] for lane in LANES]
    vectors = embed_texts(texts)
    lanes: dict[str, list[dict]] = {}
    for i, lane in enumerate(LANES):
        results = search(book_id, vectors[i], k)
        for item in results:
            item["lane"] = lane
        lanes[lane] = results

    opening = opening_chunks(book_id, n=2)
    for item in opening:
        item["lane"] = "setting"
    seen = {c.get("chunk_id") for c in lanes["setting"]}
    for item in opening:
        if item.get("chunk_id") not in seen:
            lanes["setting"].append(item)
            seen.add(item.get("chunk_id"))
    return lanes
