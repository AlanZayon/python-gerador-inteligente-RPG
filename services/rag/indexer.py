"""PDF indexing pipeline — run once per unique book (fingerprint-deduped)."""

from __future__ import annotations

import logging
from pathlib import Path

from services.rag.book_registry import find_existing_book, upsert_book_index
from services.rag.chunking import chunk_text
from services.rag.config import (
    RAG_CHUNK_MAX_TOKENS,
    RAG_CHUNK_MIN_TOKENS,
    RAG_CHUNK_OVERLAP_TOKENS,
    RAG_EMBED_MODEL,
)
from services.rag.faiss_store import book_index_path, build_and_save, index_exists
from services.rag.fingerprint import fingerprint_pdf, text_sha256
from services.rag.pdf_text import clean_text, extract_text_from_pdf, validate_pdf

logger = logging.getLogger(__name__)


def index_book(
    pdf_path: str,
    book_id: str,
    *,
    force: bool = False,
    source_filename: str | None = None,
    sha256: str | None = None,
    pages: list[dict] | None = None,
    page_count: int | None = None,
    cleaned_text: str | None = None,
) -> dict:
    """
    Index a PDF for RAG retrieval.

    Steps: validate → extract → clean → chunk → embed → FAISS persist.
    Returns summary dict with book_id, chunk_count, index_path.
    """
    if index_exists(book_id) and not force:
        from services.rag.faiss_store import get_book_meta

        meta = get_book_meta(book_id)
        return {
            "book_id": book_id,
            "chunk_count": meta.get("chunk_count", 0),
            "index_path": str(book_index_path(book_id)),
            "skipped": True,
            "index_reused": True,
            "message": "Index already exists. Use force=True to rebuild.",
        }

    is_valid, msg = validate_pdf(pdf_path)
    if not is_valid:
        raise ValueError(msg)

    raw = cleaned_text
    if raw is None:
        extracted = extract_text_from_pdf(pdf_path)
        if not extracted or len(extracted.strip()) < 100:
            raise ValueError("Insufficient text extracted from PDF.")
        raw = clean_text(extracted)
        if not raw or len(raw.strip()) < 100:
            raise ValueError("Insufficient text extracted from PDF.")

    chunks = chunk_text(
        raw,
        min_tokens=RAG_CHUNK_MIN_TOKENS,
        max_tokens=RAG_CHUNK_MAX_TOKENS,
        overlap_tokens=RAG_CHUNK_OVERLAP_TOKENS,
    )
    if not chunks:
        raise ValueError("No chunks produced from PDF text.")

    digest = sha256 or ""
    text_hash = text_sha256(raw)
    meta = {
        "source_pdf": source_filename or Path(pdf_path).name,
        "source_pdf_hash": digest[:16] if digest else "",
        "sha256": digest,
        "text_sha256": text_hash,
        "embed_model": RAG_EMBED_MODEL,
        "chunk_min_tokens": RAG_CHUNK_MIN_TOKENS,
        "chunk_max_tokens": RAG_CHUNK_MAX_TOKENS,
        "chunk_overlap_tokens": RAG_CHUNK_OVERLAP_TOKENS,
        "page_count": page_count,
    }

    index_path = build_and_save(book_id, chunks, meta=meta)
    logger.info("Indexed book_id=%s chunks=%d", book_id, len(chunks))

    try:
        upsert_book_index(
            book_id=book_id,
            sha256=digest or text_hash,
            page_count=page_count or 0,
            pages=pages or [],
            text_sha256=text_hash,
            chunk_count=len(chunks),
            embed_model=RAG_EMBED_MODEL,
        )
    except Exception as exc:
        logger.warning("Failed to persist book registry row: %s", exc)

    return {
        "book_id": book_id,
        "chunk_count": len(chunks),
        "index_path": str(index_path),
        "skipped": False,
        "index_reused": False,
        "text_sha256": text_hash,
        "sha256": digest,
    }


def ensure_indexed(
    pdf_path: str,
    *,
    source_filename: str | None = None,
    force: bool = False,
) -> dict:
    """
    Fingerprint the PDF, reuse an existing FAISS index when it matches,
    otherwise extract/chunk/embed once and register the book.
    """
    fingerprint = fingerprint_pdf(pdf_path)
    existing = find_existing_book(fingerprint)
    if existing and index_exists(existing.book_id) and not force:
        logger.info("Reusing index for book_id=%s", existing.book_id)
        return {
            "book_id": existing.book_id,
            "chunk_count": existing.chunk_count,
            "index_path": str(book_index_path(existing.book_id)),
            "skipped": True,
            "index_reused": True,
            "sha256": fingerprint["sha256"],
            "fingerprint": fingerprint,
        }

    extracted = extract_text_from_pdf(pdf_path)
    if not extracted or len(extracted.strip()) < 100:
        raise ValueError("Insufficient text extracted from PDF.")
    cleaned = clean_text(extracted)
    if not cleaned or len(cleaned.strip()) < 100:
        raise ValueError("Insufficient text extracted from PDF.")

    text_hash = text_sha256(cleaned)
    if not existing:
        existing = find_existing_book(fingerprint, text_hash=text_hash)

    book_id = existing.book_id if existing else fingerprint["book_id"]
    if existing and index_exists(book_id) and not force:
        logger.info("Reusing index via text hash for book_id=%s", book_id)
        return {
            "book_id": book_id,
            "chunk_count": existing.chunk_count,
            "index_path": str(book_index_path(book_id)),
            "skipped": True,
            "index_reused": True,
            "sha256": fingerprint["sha256"],
            "fingerprint": fingerprint,
        }

    result = index_book(
        pdf_path,
        book_id,
        force=force,
        source_filename=source_filename,
        sha256=fingerprint["sha256"],
        pages=fingerprint["pages"],
        page_count=fingerprint["page_count"],
        cleaned_text=cleaned,
    )
    result["fingerprint"] = fingerprint
    result["index_reused"] = False
    return result
