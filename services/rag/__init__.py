"""Simple RAG pipeline: PDF index (FAISS) + LLaMA generation."""

__all__ = ["index_book", "generate_campaign"]


def __getattr__(name: str):
    if name == "index_book":
        from services.rag.indexer import index_book

        return index_book
    if name == "generate_campaign":
        from services.rag.generator import generate_campaign

        return generate_campaign
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
