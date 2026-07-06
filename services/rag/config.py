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

# How many chunks to inject into the generation prompt
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))

# llama.cpp HTTP server (llama-server)
LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "llama-3-8b")
LLAMA_N_PREDICT = int(os.getenv("LLAMA_N_PREDICT", "4096"))
LLAMA_TEMPERATURE = float(os.getenv("LLAMA_TEMPERATURE", "0.7"))
LLAMA_TIMEOUT = int(os.getenv("LLAMA_TIMEOUT", "600"))
