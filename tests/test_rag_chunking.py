"""Tests for RAG text chunking."""

from unittest.mock import patch

from services.rag.chunking import chunk_text


def _fake_count_tokens(text: str) -> int:
    """Approximate token count without loading embedding model."""
    return max(1, len(text.split()))


@patch("services.rag.chunking.count_tokens", side_effect=_fake_count_tokens)
def test_chunk_text_respects_max_tokens(mock_count):
    # Short paragraphs so chunker can merge/split predictably
    paragraph = "word " * 60
    text = (paragraph.strip() + "\n\n") * 8

    chunks = chunk_text(text, min_tokens=50, max_tokens=100, overlap_tokens=10)

    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk["token_count"] <= 110
        assert chunk["text"].strip()


@patch("services.rag.chunking.count_tokens", side_effect=_fake_count_tokens)
def test_chunk_text_overlap_preserves_context(mock_count):
    text = "\n\n".join([f"Section {i}. " + "detail " * 30 for i in range(8)])

    chunks = chunk_text(text, min_tokens=40, max_tokens=80, overlap_tokens=15)

    assert len(chunks) >= 2
    # Later chunks should start with overlap from previous content
    if len(chunks) >= 2:
        words_chunk0 = set(chunks[0]["text"].split()[-10:])
        words_chunk1 = set(chunks[1]["text"].split()[:20:])
        assert words_chunk0 & words_chunk1
