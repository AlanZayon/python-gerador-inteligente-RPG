"""RAG configuration from environment variables."""

import os
from pathlib import Path

# Filesystem root for FAISS indexes — one subdir per book_id
RAG_INDEX_DIR = Path(os.getenv("RAG_INDEX_DIR", "./data/indexes"))

# sentence-transformers model (CPU-friendly, multilingual PT/EN)
RAG_EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

# Chunk sizing in tokens (counted via embedding model tokenizer)
RAG_CHUNK_MIN_TOKENS = int(os.getenv("RAG_CHUNK_MIN_TOKENS", "500"))
RAG_CHUNK_MAX_TOKENS = int(os.getenv("RAG_CHUNK_MAX_TOKENS", "800"))
RAG_CHUNK_OVERLAP_TOKENS = int(os.getenv("RAG_CHUNK_OVERLAP_TOKENS", "100"))

# How many chunks to retrieve per coverage query
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "8"))

# Book-context token floors/ceilings by complexity (quality-first, not a diet)
RAG_CONTEXT_FLOOR_SIMPLES = int(os.getenv("RAG_CONTEXT_FLOOR_SIMPLES", "2500"))
RAG_CONTEXT_CEILING_SIMPLES = int(os.getenv("RAG_CONTEXT_CEILING_SIMPLES", "4000"))
RAG_CONTEXT_FLOOR_MEDIANA = int(os.getenv("RAG_CONTEXT_FLOOR_MEDIANA", "4000"))
RAG_CONTEXT_CEILING_MEDIANA = int(os.getenv("RAG_CONTEXT_CEILING_MEDIANA", "6500"))
RAG_CONTEXT_FLOOR_COMPLEXA = int(os.getenv("RAG_CONTEXT_FLOOR_COMPLEXA", "5500"))
RAG_CONTEXT_CEILING_COMPLEXA = int(os.getenv("RAG_CONTEXT_CEILING_COMPLEXA", "9000"))

CONTEXT_BUDGETS = {
    "simples": (RAG_CONTEXT_FLOOR_SIMPLES, RAG_CONTEXT_CEILING_SIMPLES),
    "mediana": (RAG_CONTEXT_FLOOR_MEDIANA, RAG_CONTEXT_CEILING_MEDIANA),
    "complexa": (RAG_CONTEXT_FLOOR_COMPLEXA, RAG_CONTEXT_CEILING_COMPLEXA),
}

# 9router (OpenAI-compatible). LLAMA_* kept as legacy aliases.
LLAMA_BASE_URL = os.getenv("NINEROUTER_URL", os.getenv("LLAMA_BASE_URL", "http://localhost:20128")).rstrip("/")
LLAMA_MODEL = os.getenv("LLM_MODEL", os.getenv("LLAMA_MODEL", "my-combo"))
LLAMA_N_PREDICT = int(os.getenv("LLM_MAX_TOKENS", os.getenv("LLAMA_N_PREDICT", "8192")))
LLAMA_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", os.getenv("LLAMA_TEMPERATURE", "0.7")))
LLAMA_TIMEOUT = int(os.getenv("LLM_TIMEOUT", os.getenv("LLAMA_TIMEOUT", "600")))
