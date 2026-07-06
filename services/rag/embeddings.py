"""Embedding model wrapper — lazy-loaded sentence-transformers on CPU."""

import logging

import numpy as np

from services.rag.config import RAG_EMBED_MODEL

logger = logging.getLogger(__name__)

_model = None
_tokenizer = None


def _load_model():
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model: %s", RAG_EMBED_MODEL)
    _model = SentenceTransformer(RAG_EMBED_MODEL, device="cpu")
    # First module is typically the transformer with tokenizer
    _tokenizer = _model.tokenizer
    return _model, _tokenizer


def count_tokens(text: str) -> int:
    """Token count using the embedding model's tokenizer."""
    _, tokenizer = _load_model()
    return len(tokenizer.encode(text, add_special_tokens=False))


def embed_texts(texts: list[str], batch_size: int = 32) -> np.ndarray:
    """
    Embed texts and L2-normalize for cosine similarity via inner product.

    Returns float32 array shape (n, dim).
    """
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    model, _ = _load_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return vectors.astype(np.float32)
