"""Lookup order tests for book registry (DB session mocked)."""

from unittest.mock import MagicMock, patch

from services.rag.book_registry import find_existing_book


def test_lookup_prefers_sha256_hit():
    sha_hit = MagicMock(book_id="bk_sha")
    with (
        patch("services.rag.book_registry.get_by_sha256", return_value=sha_hit),
        patch("services.rag.book_registry.find_perceptual_match") as perceptual,
        patch("services.rag.book_registry.get_by_text_sha256") as text_hit,
    ):
        found = find_existing_book({"sha256": "abc", "page_count": 10, "pages": []})
    assert found is sha_hit
    perceptual.assert_not_called()
    text_hit.assert_not_called()


def test_lookup_uses_perceptual_when_sha_misses():
    perc_hit = MagicMock(book_id="bk_perc")
    with (
        patch("services.rag.book_registry.get_by_sha256", return_value=None),
        patch("services.rag.book_registry.find_perceptual_match", return_value=perc_hit),
        patch("services.rag.book_registry.get_by_text_sha256") as text_hit,
    ):
        found = find_existing_book({"sha256": "abc", "page_count": 10, "pages": []})
    assert found is perc_hit
    text_hit.assert_not_called()


def test_lookup_falls_back_to_text_hash():
    text_row = MagicMock(book_id="bk_text")
    with (
        patch("services.rag.book_registry.get_by_sha256", return_value=None),
        patch("services.rag.book_registry.find_perceptual_match", return_value=None),
        patch("services.rag.book_registry.get_by_text_sha256", return_value=text_row),
    ):
        found = find_existing_book(
            {"sha256": "abc", "page_count": 10, "pages": []},
            text_hash="ffff",
        )
    assert found is text_row


def test_lookup_miss_returns_none():
    with (
        patch("services.rag.book_registry.get_by_sha256", return_value=None),
        patch("services.rag.book_registry.find_perceptual_match", return_value=None),
        patch("services.rag.book_registry.get_by_text_sha256", return_value=None),
    ):
        found = find_existing_book({"sha256": "abc", "page_count": 3, "pages": []}, text_hash="x")
    assert found is None
