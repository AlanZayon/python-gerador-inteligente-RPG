#!/usr/bin/env python
"""
Offline PDF indexing for RAG.

Usage:
    python scripts/index_book.py --pdf livro.pdf --book-id meu-livro
    python scripts/index_book.py --pdf livro.pdf --book-id meu-livro --force

Requires: pip install -r requirements.txt (faiss-cpu, sentence-transformers, PyMuPDF)
First run downloads the embedding model (~100MB).
"""

import argparse
import sys
from pathlib import Path

# Allow running from repo root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from services.rag.indexer import index_book  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Index an RPG PDF for RAG retrieval")
    parser.add_argument("--pdf", required=True, help="Path to rulebook PDF")
    parser.add_argument("--book-id", required=True, help="Unique book identifier (slug)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild index even if it already exists",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    try:
        result = index_book(str(pdf_path), args.book_id, force=args.force)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if result.get("skipped"):
        print(f"Skipped (index exists): {result['book_id']} — use --force to rebuild")
    else:
        print(f"Indexed: {result['book_id']}")
        print(f"  Chunks: {result['chunk_count']}")
        print(f"  Path:   {result['index_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
