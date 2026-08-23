"""PDF identity: SHA-256 plus aHash / dHash / pHash / wHash of sampled pages."""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

import fitz
import imagehash
from PIL import Image

logger = logging.getLogger(__name__)

HAMMING_THRESHOLD = int(os.getenv("RAG_HAMMING_THRESHOLD", "10"))
MAX_SAMPLE_PAGES = int(os.getenv("RAG_FINGERPRINT_PAGES", "6"))
PAGE_WIDTH_PX = 256
PAGE_COUNT_TOLERANCE = 0.15
HASH_KEYS = ("ahash", "dhash", "phash", "whash")


def file_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def text_sha256(text: str) -> str:
    normalized = " ".join((text or "").split()).strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def book_id_from_sha256(sha256: str) -> str:
    return f"bk_{sha256[:16]}"


def sample_page_indices(n_pages: int, max_pages: int = MAX_SAMPLE_PAGES) -> list[int]:
    if n_pages <= 0:
        return []
    if n_pages <= max_pages:
        return list(range(n_pages))
    indices = {0, n_pages - 1}
    mid_count = max_pages - 2
    for i in range(1, mid_count + 1):
        indices.add(round(i * (n_pages - 1) / (mid_count + 1)))
    return sorted(indices)


def hash_image(image: Image.Image) -> dict[str, str]:
    rgb = image.convert("RGB")
    return {
        "ahash": str(imagehash.average_hash(rgb)),
        "dhash": str(imagehash.dhash(rgb)),
        "phash": str(imagehash.phash(rgb)),
        "whash": str(imagehash.whash(rgb)),
    }


def _page_to_image(page: fitz.Page, width_px: int = PAGE_WIDTH_PX) -> Image.Image:
    rect = page.rect
    zoom = width_px / rect.width if rect.width else 1.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    mode = "RGB" if pix.n < 4 else "RGBA"
    image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    if mode != "RGB":
        image = image.convert("RGB")
    return image


def fingerprint_pdf(file_path: str) -> dict[str, Any]:
    """Return sha256, page_count, and perceptual hashes for sampled pages."""
    sha256 = file_sha256(file_path)
    pages: list[dict[str, Any]] = []
    with fitz.open(file_path) as doc:
        page_count = len(doc)
        for idx in sample_page_indices(page_count):
            image = _page_to_image(doc.load_page(idx))
            hashes = hash_image(image)
            pages.append({"page": idx, **hashes})
    return {
        "sha256": sha256,
        "book_id": book_id_from_sha256(sha256),
        "page_count": page_count,
        "pages": pages,
    }


def hamming_distance(hex_a: str, hex_b: str) -> int:
    return imagehash.hex_to_hash(hex_a) - imagehash.hex_to_hash(hex_b)


def mean_hamming(pages_a: list[dict], pages_b: list[dict]) -> float | None:
    n = min(len(pages_a or []), len(pages_b or []))
    if n == 0:
        return None
    total = 0
    count = 0
    for i in range(n):
        for key in HASH_KEYS:
            a = pages_a[i].get(key)
            b = pages_b[i].get(key)
            if not a or not b:
                continue
            try:
                total += hamming_distance(a, b)
                count += 1
            except Exception:
                logger.debug("Hamming compare failed for %s", key, exc_info=True)
    if count == 0:
        return None
    return total / count


def page_count_compatible(count_a: int, count_b: int) -> bool:
    hi = max(count_a, count_b, 1)
    return abs(count_a - count_b) / hi <= PAGE_COUNT_TOLERANCE


def fingerprints_match(
    fp_a: dict,
    fp_b: dict,
    threshold: int = HAMMING_THRESHOLD,
) -> bool:
    if not page_count_compatible(int(fp_a.get("page_count") or 0), int(fp_b.get("page_count") or 0)):
        return False
    distance = mean_hamming(fp_a.get("pages") or [], fp_b.get("pages") or [])
    return distance is not None and distance <= threshold
