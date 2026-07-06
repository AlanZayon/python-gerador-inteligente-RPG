"""PDF text extraction and cleaning — no AI, PyMuPDF only."""

import logging
import re

import fitz

logger = logging.getLogger(__name__)

# Page markers from legacy extractor; stripped during clean
_PAGE_MARKER = re.compile(r"---\s*P[aá]gina\s+\d+\s*---", re.IGNORECASE)


def validate_pdf(file_path: str) -> tuple[bool, str]:
    """Check PDF is readable and within page limit (max 500)."""
    try:
        with fitz.open(file_path) as doc:
            page_count = len(doc)
        if page_count == 0:
            return False, "Empty PDF"
        if page_count > 500:
            return False, "PDF too large (max 500 pages)"
        return True, "OK"
    except Exception:
        return False, "Corrupted or unreadable PDF"


def extract_text_from_pdf(file_path: str) -> str:
    """Extract raw text from PDF, one page marker per page."""
    try:
        full_text = ""
        with fitz.open(file_path) as doc:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                full_text += f"\n--- Página {page_num + 1} ---\n{page.get_text()}"
        return full_text
    except Exception as exc:
        logger.error("Text extraction failed: %s", exc)
        return ""


def clean_text(raw: str) -> str:
    """
    Normalize extracted PDF text for chunking.

    - Remove page markers
    - Collapse whitespace
    - Drop short lines that repeat often (likely headers/footers)
    """
    text = _PAGE_MARKER.sub("\n", raw)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = [ln.strip() for ln in text.splitlines()]
    line_counts: dict[str, int] = {}
    for ln in lines:
        if 0 < len(ln) <= 80:
            line_counts[ln] = line_counts.get(ln, 0) + 1

    # Lines repeated 3+ times across the book are treated as boilerplate
    boilerplate = {ln for ln, count in line_counts.items() if count >= 3}
    cleaned_lines = [ln for ln in lines if ln and ln not in boilerplate]

    return "\n".join(cleaned_lines).strip()
