"""FAISS vector store — build, persist, load, search per book_id."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np

from services.rag.config import RAG_INDEX_DIR
from services.rag.embeddings import embed_texts

logger = logging.getLogger(__name__)

INDEX_FILENAME = "index.faiss"
CHUNKS_FILENAME = "chunks.json"
META_FILENAME = "meta.json"


class BookIndexNotFoundError(FileNotFoundError):
    pass


def book_index_path(book_id: str) -> Path:
    return RAG_INDEX_DIR / book_id


def index_exists(book_id: str) -> bool:
    path = book_index_path(book_id)
    return (path / INDEX_FILENAME).exists() and (path / CHUNKS_FILENAME).exists()


def get_book_meta(book_id: str) -> dict:
    meta_path = book_index_path(book_id) / META_FILENAME
    if not meta_path.exists():
        if not index_exists(book_id):
            raise BookIndexNotFoundError(f"No index for book_id={book_id}")
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def save_index(
    book_id: str,
    chunks: list[dict],
    vectors: np.ndarray,
    meta: dict | None = None,
) -> Path:
    """Persist FAISS index, chunks, and metadata to disk."""
    out_dir = book_index_path(book_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    if vectors.shape[0] != len(chunks):
        raise ValueError("vectors row count must match chunks length")

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    faiss.write_index(index, str(out_dir / INDEX_FILENAME))
    (out_dir / CHUNKS_FILENAME).write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    meta_payload = {
        "book_id": book_id,
        "chunk_count": len(chunks),
        "embedding_dim": dim,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **(meta or {}),
    }
    (out_dir / META_FILENAME).write_text(
        json.dumps(meta_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Saved index for %s (%d chunks) at %s", book_id, len(chunks), out_dir)
    return out_dir


def load_index(book_id: str) -> tuple[faiss.Index, list[dict], dict]:
    out_dir = book_index_path(book_id)
    index_path = out_dir / INDEX_FILENAME
    chunks_path = out_dir / CHUNKS_FILENAME

    if not index_path.exists() or not chunks_path.exists():
        raise BookIndexNotFoundError(f"No index for book_id={book_id}")

    index = faiss.read_index(str(index_path))
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    meta = get_book_meta(book_id)
    return index, chunks, meta


def build_and_save(book_id: str, chunks: list[dict], meta: dict | None = None) -> Path:
    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)
    return save_index(book_id, chunks, vectors, meta=meta)


def opening_chunks(book_id: str, n: int = 2) -> list[dict]:
    """Return the first n stored chunks (typically the start of the book)."""
    _, chunks, _ = load_index(book_id)
    out = []
    for chunk in chunks[:n]:
        out.append(
            {
                "chunk_id": chunk["id"],
                "text": chunk["text"],
                "score": 0.0,
                "token_count": chunk.get("token_count"),
            }
        )
    return out


def search(
    book_id: str,
    query_vector: np.ndarray,
    top_k: int,
) -> list[dict]:
    """
    Search FAISS index. query_vector shape (dim,) or (1, dim).

    Returns list of {chunk_id, text, score, token_count}.
    """
    index, chunks, _ = load_index(book_id)

    if query_vector.ndim == 1:
        query_vector = query_vector.reshape(1, -1)
    query_vector = query_vector.astype(np.float32)

    k = min(top_k, len(chunks))
    if k == 0:
        return []

    scores, indices = index.search(query_vector, k)
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        chunk = chunks[idx]
        results.append(
            {
                "chunk_id": chunk["id"],
                "text": chunk["text"],
                "score": float(score),
                "token_count": chunk.get("token_count"),
            }
        )
    return results
