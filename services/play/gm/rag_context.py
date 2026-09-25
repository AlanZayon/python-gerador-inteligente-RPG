"""Scoped rulebook retrieval for GameMasterRuntime (not full-book injection)."""

from __future__ import annotations

import logging
from typing import Any, Callable

from services.rag.retrieval import mechanics_query_for_preset

logger = logging.getLogger(__name__)

RetrieveFn = Callable[..., list[dict]]


def _normalize_excerpts(chunks: list[dict], top_k: int) -> list[dict[str, Any]]:
    excerpts: list[dict[str, Any]] = []
    for chunk in (chunks or [])[:top_k]:
        text = (chunk.get("text") or chunk.get("content") or "").strip()
        if not text:
            continue
        excerpts.append(
            {
                "text": text[:1200],
                "score": chunk.get("score"),
                "chunk_id": chunk.get("id") or chunk.get("chunk_id"),
            }
        )
    return excerpts


def build_gm_query(
    player_action: str,
    scene: str = "",
    location: str = "",
    character_name: str = "",
    system_preset: str | None = None,
) -> str:
    action = (player_action or "").strip()
    lower = action.lower()
    combatish = any(
        kw in lower
        for kw in (
            "attack",
            "combat",
            "fight",
            "initiative",
            "strike",
            "shoot",
            "damage",
            "hit",
            "ataque",
            "combate",
            "luta",
            "iniciativa",
            "dano",
            "ferir",
            "golpe",
        )
    )
    parts = [
        mechanics_query_for_preset(system_preset),
        "RPG rules, checks, difficulty, and when to call for a roll.",
    ]
    if combatish:
        parts.append(
            "combat initiative attack damage defense armor hit points "
            "conditions wounds turn order"
        )
    parts.append(f"Player action: {action[:300]}")
    if scene:
        parts.append(f"Current scene: {scene}")
    if location:
        parts.append(f"Location: {location}")
    if character_name:
        parts.append(f"Acting character: {character_name}")
    return " ".join(parts)


def _default_retrieve(*, book_id: str, query: str, top_k: int = 4, **_):
    from services.rag.embeddings import embed_texts
    from services.rag.faiss_store import index_exists, search

    if not index_exists(book_id):
        return []
    vec = embed_texts([query])[0]
    return search(book_id, vec, top_k)


def retrieve_gm_rules(
    *,
    book_id: str | None,
    player_action: str,
    scene: str = "",
    location: str = "",
    character_name: str = "",
    system_preset: str | None = None,
    top_k: int = 4,
    retrieve_fn: RetrieveFn | None = None,
) -> list[dict[str, Any]]:
    """Return a small set of rulebook excerpts for the current beat."""
    if not book_id:
        return []

    query = build_gm_query(
        player_action,
        scene=scene,
        location=location,
        character_name=character_name,
        system_preset=system_preset,
    )
    return lookup_rule_excerpts(
        book_id=book_id,
        query=query,
        top_k=top_k,
        retrieve_fn=retrieve_fn,
    )


def lookup_rule_excerpts(
    *,
    book_id: str | None,
    query: str,
    top_k: int = 4,
    retrieve_fn: RetrieveFn | None = None,
) -> list[dict[str, Any]]:
    """Search the BookIndex with an explicit query (GM Tool lookup_rules)."""
    if not book_id:
        return []
    k = max(1, min(int(top_k or 4), 4))
    q = (query or "").strip() or "RPG game mechanics checks difficulty"
    fn = retrieve_fn or _default_retrieve
    try:
        chunks = fn(book_id=book_id, query=q, top_k=k) or []
    except Exception as exc:  # noqa: BLE001
        logger.info("GM RAG retrieve skipped: %s", exc)
        return []
    return _normalize_excerpts(chunks, k)
