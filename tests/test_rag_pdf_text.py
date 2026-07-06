"""Tests for PDF text cleaning."""

from services.rag.pdf_text import clean_text


def test_clean_text_removes_page_markers():
    raw = "--- Página 1 ---\nHello world\n\n--- Página 2 ---\nMore text"
    cleaned = clean_text(raw)
    assert "Página" not in cleaned
    assert "Hello world" in cleaned
    assert "More text" in cleaned


def test_clean_text_removes_repeated_headers():
    raw = "\n".join(["Chapter Header"] * 5 + ["Unique content paragraph here."] * 2)
    cleaned = clean_text(raw)
    assert "Chapter Header" not in cleaned
    assert "Unique content" in cleaned
