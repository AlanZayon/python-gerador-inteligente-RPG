"""Offline PDF indexing pipeline — run once per book."""

import hashlib
import logging
from pathlib import Path

from services.rag.chunking import chunk_text
from services.rag.config import (
    RAG_CHUNK_MAX_TOKENS,
    RAG_CHUNK_MIN_TOKENS,
    RAG_CHUNK_OVERLAP_TOKENS,
    RAG_EMBED_MODEL,
)
from services.rag.faiss_store import build_and_save, index_exists
from services.rag.pdf_text import clean_text, extract_text_from_pdf, validate_pdf

logger = logging.getLogger(__name__)


def _pdf_hash(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()[:16]


def index_book(
    pdf_path: str,
    book_id: str,
    *,
    force: bool = False,
    source_filename: str | None = None,
) -> dict:
    """
    Index a PDF for RAG retrieval.

    Steps: validate → extract → clean → chunk → embed → FAISS persist.
    Returns summary dict with book_id, chunk_count, index_path.
    """
    if index_exists(book_id) and not force:
        from services.rag.faiss_store import get_book_meta, book_index_path

        meta = get_book_meta(book_id)
        return {
            "book_id": book_id,
            "chunk_count": meta.get("chunk_count", 0),
            "index_path": str(book_index_path(book_id)),
            "skipped": True,
            "message": "Index already exists. Use force=True to rebuild.",
        }

    is_valid, msg = validate_pdf(pdf_path)
    if not is_valid:
        raise ValueError(msg)

    raw = extract_text_from_pdf(pdf_path)
    if not raw or len(raw.strip()) < 100:
        raise ValueError("Insufficient text extracted from PDF.")

    cleaned = clean_text(raw)
    chunks = chunk_text(
        cleaned,
        min_tokens=RAG_CHUNK_MIN_TOKENS,
        max_tokens=RAG_CHUNK_MAX_TOKENS,
        overlap_tokens=RAG_CHUNK_OVERLAP_TOKENS,
    )
    if not chunks:
        raise ValueError("No chunks produced from PDF text.")

    meta = {
        "source_pdf": source_filename or Path(pdf_path).name,
        "source_pdf_hash": _pdf_hash(pdf_path),
        "embed_model": RAG_EMBED_MODEL,
        "chunk_min_tokens": RAG_CHUNK_MIN_TOKENS,
        "chunk_max_tokens": RAG_CHUNK_MAX_TOKENS,
        "chunk_overlap_tokens": RAG_CHUNK_OVERLAP_TOKENS,
    }

    index_path = build_and_save(book_id, chunks, meta=meta)
    logger.info("Indexed book_id=%s chunks=%d", book_id, len(chunks))

    return {
        "book_id": book_id,
        "chunk_count": len(chunks),
        "index_path": str(index_path),
        "skipped": False,
    }
