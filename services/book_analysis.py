"""Map-reduce book analysis for campaign generation."""

import json
import logging
import os
import re

from services.llm_client import complete, is_configured, model_lite

logger = logging.getLogger(__name__)

CHUNK_SIZE = int(os.getenv("BOOK_BIBLE_CHUNK_SIZE", "8000"))


def split_text_chunks(full_text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    if len(full_text) <= chunk_size:
        return [full_text]
    chunks = []
    pages = re.split(r"\n--- Página \d+ ---\n", full_text)
    for page in pages:
        if not page.strip():
            continue
        if len(page) <= chunk_size:
            if chunks and len(chunks[-1]) + len(page) + 1 <= chunk_size:
                chunks[-1] += "\n" + page
            elif chunks and len(chunks[-1]) < chunk_size:
                chunks.append(page)
            else:
                chunks.append(page)
        else:
            for i in range(0, len(page), chunk_size):
                chunks.append(page[i : i + chunk_size])
    if not chunks:
        for i in range(0, len(full_text), chunk_size):
            chunks.append(full_text[i : i + chunk_size])
    return chunks


def _summarize_chunk(chunk: str, index: int, total: int, model_name: str) -> str:
    prompt = f"""Summarize this RPG book excerpt (part {index + 1}/{total}). Extract:
- Setting and world tone
- Game system hints (D&D, Pathfinder, etc.)
- Key factions, locations, creatures, mechanics
- Notable terminology (5-10 terms)

Be concise bullet points. Excerpt:
{chunk[:12000]}
"""
    try:
        return complete(prompt, model=model_name, temperature=0.3)
    except Exception as exc:
        logger.warning("Chunk summary failed: %s", exc)
        return ""


def _merge_summaries(summaries: list[str], model_name: str) -> dict:
    combined = "\n\n---\n\n".join(s for s in summaries if s.strip())
    prompt = f"""Merge these RPG book summaries into one JSON object with keys:
setting, system, tone, factions, locations, creatures, key_terms (array of 5-10 strings), mechanics_notes

Return ONLY valid JSON, no markdown fences.

Summaries:
{combined[:20000]}
"""
    try:
        text = complete(prompt, model=model_name, temperature=0.2).strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)
    except Exception as exc:
        logger.warning("Merge summaries failed: %s", exc)
        return {
            "setting": "Fantasy world derived from uploaded rulebook",
            "system": "generic",
            "tone": "adventurous",
            "factions": [],
            "locations": [],
            "creatures": [],
            "key_terms": [],
            "mechanics_notes": combined[:2000] if combined else "",
        }


def build_book_bible(full_text: str, model_name: str | None = None) -> dict:
    """Build structured book bible via map-reduce summarization."""
    if not is_configured():
        return {
            "setting": "Generic fantasy setting",
            "system": "generic",
            "tone": "adventurous",
            "key_terms": [],
            "mechanics_notes": full_text[:3000],
        }

    name = model_name or model_lite()
    chunks = split_text_chunks(full_text)
    summaries = [_summarize_chunk(c, i, len(chunks), name) for i, c in enumerate(chunks[:12])]
    bible = _merge_summaries(summaries, name)
    if not bible.get("key_terms"):
        bible["key_terms"] = _extract_terms_heuristic(full_text)
    return bible


def _extract_terms_heuristic(text: str, limit: int = 8) -> list[str]:
    words = re.findall(r"\b[A-Z][a-z]{3,}\b", text)
    seen: set[str] = set()
    terms: list[str] = []
    for w in words:
        if w.lower() not in {"page", "chapter", "section", "table"} and w not in seen:
            seen.add(w)
            terms.append(w)
            if len(terms) >= limit:
                break
    return terms


def format_inspired_block(bible: dict) -> str:
    terms = bible.get("key_terms") or []
    setting = bible.get("setting", "")
    locations = bible.get("locations") or []
    snippets = terms[:5]
    if isinstance(locations, list):
        snippets.extend(str(x) for x in locations[:2])
    unique = list(dict.fromkeys(snippets))[:5]
    if not unique:
        return ""
    items = "\n".join(f"- {t}" for t in unique)
    return f"\n\n## Inspired by your book\n{items}\n_Setting: {setting[:120]}_\n"
