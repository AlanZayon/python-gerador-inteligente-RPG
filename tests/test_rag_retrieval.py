"""Tests for FAISS retrieval."""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from services.rag.faiss_store import save_index, search
from services.rag.retrieval import build_query, retrieve


@pytest.fixture
def temp_index(tmp_path, monkeypatch):
    monkeypatch.setattr("services.rag.faiss_store.RAG_INDEX_DIR", tmp_path)

    chunks = [
        {"id": 0, "text": "Dark horror creatures lurk in haunted forests.", "token_count": 10},
        {"id": 1, "text": "Political intrigue among noble houses and courtly diplomacy.", "token_count": 10},
        {"id": 2, "text": "Heroic knights defend the realm from dragon attacks.", "token_count": 10},
    ]
    vectors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    save_index("test-book", chunks, vectors, meta={"source_pdf": "test.pdf"})
    return tmp_path / "test-book"


def test_build_query_includes_theme_and_hook():
    q = build_query("dark fantasy", "A sunken city rises")
    assert "dark fantasy" in q
    assert "sunken city" in q.lower()


@patch("services.rag.retrieval.embed_texts")
def test_retrieve_returns_relevant_chunk(mock_embed, temp_index):
    # Query vector closest to horror chunk (index 0)
    mock_embed.return_value = np.array([[0.95, 0.05, 0.0]], dtype=np.float32)

    results = retrieve("test-book", theme="horror", hook="", top_k=1)

    assert len(results) == 1
    assert "horror" in results[0]["text"].lower()
    assert results[0]["score"] > 0.5


def test_search_returns_top_k(temp_index):
    query = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    results = search("test-book", query, top_k=2)

    assert len(results) == 2
    assert results[0]["chunk_id"] == 1
    assert "Political" in results[0]["text"]
