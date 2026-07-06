"""Split cleaned text into overlapping token-sized chunks."""

from services.rag.config import (
    RAG_CHUNK_MAX_TOKENS,
    RAG_CHUNK_MIN_TOKENS,
    RAG_CHUNK_OVERLAP_TOKENS,
)
from services.rag.embeddings import count_tokens


def _split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if parts:
        return parts
    return [text] if text.strip() else []


def _take_last_tokens(text: str, n_tokens: int) -> str:
    """Return suffix of text covering roughly the last n_tokens."""
    if n_tokens <= 0 or not text:
        return ""
    words = text.split()
    # Grow from end until token budget reached
    for start in range(len(words)):
        candidate = " ".join(words[start:])
        if count_tokens(candidate) >= n_tokens:
            return candidate
    return text


def chunk_text(
    text: str,
    min_tokens: int = RAG_CHUNK_MIN_TOKENS,
    max_tokens: int = RAG_CHUNK_MAX_TOKENS,
    overlap_tokens: int = RAG_CHUNK_OVERLAP_TOKENS,
) -> list[dict]:
    """
    Build chunks of min_tokens..max_tokens with overlap between consecutive chunks.

    Each chunk: {id, text, token_count, char_start}
    """
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[dict] = []
    buffer = ""
    char_start = 0

    def flush_buffer(force: bool = False) -> None:
        nonlocal buffer, char_start
        if not buffer.strip():
            return
        tok = count_tokens(buffer)
        if not force and tok < min_tokens:
            return

        chunk_id = len(chunks)
        chunks.append(
            {
                "id": chunk_id,
                "text": buffer.strip(),
                "token_count": tok,
                "char_start": char_start,
            }
        )
        overlap_prefix = _take_last_tokens(buffer, overlap_tokens)
        buffer = overlap_prefix
        if overlap_prefix:
            buffer = overlap_prefix + "\n\n"

    for para in paragraphs:
        candidate = (buffer + para).strip() if buffer else para
        tok = count_tokens(candidate)

        if tok <= max_tokens:
            if buffer and not buffer.endswith("\n\n"):
                buffer += "\n\n"
            buffer += para
            continue

        # Current buffer full — flush if big enough
        if buffer.strip():
            flush_buffer(force=count_tokens(buffer) >= min_tokens)
            if not buffer:
                char_start = text.find(para, char_start)

        # Paragraph alone may exceed max — split by sentences, then by words
        if count_tokens(para) > max_tokens:
            sentences = [s.strip() for s in para.replace(". ", ".\n").split("\n") if s.strip()]
            units = sentences if len(sentences) > 1 else para.split()
            for unit in units:
                candidate = (buffer + " " + unit).strip() if buffer else unit
                if count_tokens(candidate) > max_tokens:
                    if buffer.strip():
                        flush_buffer(force=True)
                    # Hard split oversized unit by words
                    words = unit.split()
                    word_buf = ""
                    for word in words:
                        trial = (word_buf + " " + word).strip() if word_buf else word
                        if count_tokens(trial) > max_tokens and word_buf:
                            buffer = word_buf
                            flush_buffer(force=True)
                            word_buf = word
                        else:
                            word_buf = trial
                    if word_buf:
                        buffer = word_buf
                else:
                    if buffer and not buffer.endswith(" "):
                        buffer += " "
                    buffer += unit
        else:
            buffer = para

    if buffer.strip():
        flush_buffer(force=True)

    return chunks
