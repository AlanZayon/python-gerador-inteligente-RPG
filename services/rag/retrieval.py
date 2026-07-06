"""Semantic retrieval — theme-based query, no LLM classification."""

from services.rag.config import RAG_TOP_K
from services.rag.embeddings import embed_texts
from services.rag.faiss_store import search


def build_query(theme: str, hook: str = "") -> str:
    """
    Build a retrieval query from campaign theme and optional hook.

    Fixed template — no LLM query expansion (keeps cost and complexity low).
    """
    parts = [f"RPG campaign setting and rules related to theme: {theme}"]
    if hook:
        parts.append(f"Campaign hook: {hook}")
    return ". ".join(parts)


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
