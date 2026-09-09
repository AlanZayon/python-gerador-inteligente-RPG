"""Scoped rulebook retrieval for GameMasterRuntime (not full-book injection)."""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

RetrieveFn = Callable[..., list[dict]]


def build_gm_query(
    player_action: str,
    scene: str = "",
    location: str = "",
    character_name: str = "",
) -> str:
    parts = [
        "RPG rules and rulings relevant to this live play beat.",
        f"Player action: {(player_action or '').strip()[:300]}",
    ]
    if scene:
        parts.append(f"Current scene: {scene}")
    if location:
        parts.append(f"Location: {location}")
    if character_name:
        parts.append(f"Acting character: {character_name}")
    return " ".join(parts)


def retrieve_gm_rules(
    *,
    book_id: str | None,
    player_action: str,
    scene: str = "",
    location: str = "",
    character_name: str = "",
    top_k: int = 4,
    retrieve_fn: RetrieveFn | None = None,
) -> list[dict[str, Any]]:
    """Return a small set of rulebook excerpts for the current beat."""
    if not book_id:
        return []

    query = build_gm_query(player_action, scene=scene, location=location, character_name=character_name)

    def _default_retrieve(**kwargs):
        from services.rag.embeddings import embed_texts
        from services.rag.faiss_store import index_exists, search

        bid = kwargs["book_id"]
        if not index_exists(bid):
            return []
        vec = embed_texts([kwargs["query"]])[0]
        return search(bid, vec, kwargs.get("top_k") or top_k)

    fn = retrieve_fn or _default_retrieve
    try:
        chunks = fn(book_id=book_id, query=query, top_k=top_k) or []
    except Exception as exc:  # noqa: BLE001
        logger.info("GM RAG retrieve skipped: %s", exc)
        return []

    excerpts: list[dict[str, Any]] = []
    for chunk in chunks[:top_k]:
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
