"""Persist and look up indexed books by SHA-256, text hash, or perceptual match."""

from __future__ import annotations

import json
import logging

from database import SessionLocal
from services.rag.fingerprint import fingerprints_match

logger = logging.getLogger(__name__)


def _book_index_model():
    from models.entities import BookIndex

    return BookIndex


def _row_to_fp(row) -> dict:
    try:
        pages = json.loads(row.fingerprints_json or "[]")
    except json.JSONDecodeError:
        pages = []
    return {
        "sha256": row.sha256,
        "book_id": row.book_id,
        "page_count": row.page_count,
        "pages": pages,
    }


def get_by_sha256(sha256: str):
    BookIndex = _book_index_model()
    db = SessionLocal()
    try:
        return db.query(BookIndex).filter(BookIndex.sha256 == sha256).first()
    finally:
        db.close()


def get_by_text_sha256(text_hash: str):
    if not text_hash:
        return None
    BookIndex = _book_index_model()
    db = SessionLocal()
    try:
        return db.query(BookIndex).filter(BookIndex.text_sha256 == text_hash).first()
    finally:
        db.close()


def get_by_book_id(book_id: str):
    BookIndex = _book_index_model()
    db = SessionLocal()
    try:
        return db.query(BookIndex).filter(BookIndex.book_id == book_id).first()
    finally:
        db.close()


def find_perceptual_match(fingerprint: dict):
    BookIndex = _book_index_model()
    db = SessionLocal()
    try:
        rows = db.query(BookIndex).all()
        for row in rows:
            if fingerprints_match(fingerprint, _row_to_fp(row)):
                return row
        return None
    finally:
        db.close()


def find_existing_book(
    fingerprint: dict,
    text_hash: str | None = None,
):
    """Lookup order: exact file hash, perceptual pages, optional cleaned-text hash."""
    sha256 = fingerprint.get("sha256") or ""
    if sha256:
        hit = get_by_sha256(sha256)
        if hit:
            return hit
    perceptual = find_perceptual_match(fingerprint)
    if perceptual:
        return perceptual
    if text_hash:
        return get_by_text_sha256(text_hash)
    return None


def upsert_book_index(
    *,
    book_id: str,
    sha256: str,
    page_count: int,
    pages: list[dict],
    text_sha256: str | None,
    chunk_count: int,
    embed_model: str,
):
    BookIndex = _book_index_model()
    db = SessionLocal()
    try:
        row = db.query(BookIndex).filter(BookIndex.book_id == book_id).first()
        payload = json.dumps(pages, ensure_ascii=False)
        if row:
            row.page_count = page_count
            row.fingerprints_json = payload
            if text_sha256:
                row.text_sha256 = text_sha256
            row.chunk_count = chunk_count
            row.embed_model = embed_model
        else:
            existing_sha = db.query(BookIndex).filter(BookIndex.sha256 == sha256).first()
            if existing_sha:
                return existing_sha
            row = BookIndex(
                book_id=book_id,
                sha256=sha256,
                page_count=page_count,
                fingerprints_json=payload,
                text_sha256=text_sha256,
                chunk_count=chunk_count,
                embed_model=embed_model,
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()
