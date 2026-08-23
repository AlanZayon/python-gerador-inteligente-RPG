"""Runtime RAG campaign generation — retrieve → prompt → LLaMA."""

import logging
from typing import Callable

from services.rag.config import RAG_TOP_K
from services.rag.faiss_store import BookIndexNotFoundError, index_exists
from services.rag.llama_client import complete
from services.rag.prompt_builder import build_rag_prompt
from services.rag.retrieval import retrieve

logger = logging.getLogger(__name__)

_COMPLEXITY_GUIDELINES = {
    "simple": "- 1-2 sessions of 3-4 hours\n- Linear story, 2-3 encounters\n- 1-2 NPCs, 1 main location",
    "medium": "- 3-4 sessions\n- Branching choices, 4-6 encounters\n- 3-5 NPCs, 2-3 locations",
    "complex": "- 5+ sessions\n- Non-linear arcs, 8+ encounters\n- 6+ NPCs, 4+ locations, multiple endings",
}
_COMPLEXITY_MAP = {"simples": "simple", "mediana": "medium", "complexa": "complex"}


def _complexity_guidelines(complexity: str) -> str:
    english = _COMPLEXITY_MAP.get(complexity.lower(), complexity.lower())
    return _COMPLEXITY_GUIDELINES.get(english, _COMPLEXITY_GUIDELINES["medium"])


def generate_campaign(
    *,
    book_id: str,
    theme: str,
    hook: str = "",
    target_language: str = "pt",
    system_preset: str | None = "generic",
    tone: str = "",
    party_level: str = "",
    complexity: str = "mediana",
    character_sheets: list[str] | None = None,
    top_k: int | None = None,
    llm_fn: Callable[[str], str] | None = None,
) -> dict:
    """
    Full RAG generation pipeline.

    llm_fn: injectable for tests (defaults to llama_client.complete).
    """
    if not book_id or not theme:
        raise ValueError("book_id and theme are required")

    if not index_exists(book_id):
        raise BookIndexNotFoundError(f"No index for book_id={book_id}")

    k = top_k if top_k is not None else RAG_TOP_K
    chunks = retrieve(book_id, theme, hook, top_k=k)

    guidelines = _complexity_guidelines(complexity)
    prompt = build_rag_prompt(
        chunks=chunks,
        theme=theme,
        hook=hook,
        target_language=target_language,
        system_preset=system_preset,
        tone=tone,
        party_level=party_level,
        complexity=complexity,
        character_sheets=character_sheets,
        guidelines=guidelines,
    )

    generate = llm_fn or complete
    campaign = generate(prompt)

    return {
        "campaign": campaign,
        "chunks_used": len(chunks),
        "generation_source": "9router",
        "book_id": book_id,
        "prompt_token_estimate": None,  # TODO: expose token count if needed
    }
