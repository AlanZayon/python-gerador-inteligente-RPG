"""Assemble generation prompt from retrieved chunks and user inputs."""

from services.prompt_templates import _mandatory_sections, get_system_instructions


def _format_chunks_block(chunks: list[dict]) -> str:
    if not chunks:
        return "(No book context retrieved — index may be empty.)"
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        score = chunk.get("score")
        score_str = f" (relevance {score:.2f})" if score is not None else ""
        parts.append(f"--- Excerpt {i}{score_str} ---\n{chunk['text']}")
    return "\n\n".join(parts)


def _format_character_sheets(sheets: list[str]) -> str:
    if not sheets:
        return ""
    blocks = []
    for i, text in enumerate(sheets, start=1):
        blocks.append(f"### Player {i}\n{text.strip()}")
    return "\n\n".join(blocks)


def build_rag_prompt(
    *,
    chunks: list[dict],
    theme: str,
    hook: str = "",
    target_language: str = "pt",
    system_preset: str | None = "generic",
    tone: str = "",
    party_level: str = "",
    complexity: str = "mediana",
    character_sheets: list[str] | None = None,
    guidelines: str = "",
) -> str:
    """
    Build the full prompt sent to LLaMA.

    Single-pass generation — TODO: add outline/expand multi-pass if quality is low.
    """
    sheets_text = _format_character_sheets(character_sheets or [])
    sheets_block = f"\n\nPLAYER CHARACTER SHEETS:\n{sheets_text}\n" if sheets_text else ""
    sections = _mandatory_sections(sheets_text)
    system_block = get_system_instructions(system_preset)
    book_block = _format_chunks_block(chunks)

    prefs = []
    if theme:
        prefs.append(f"Theme: {theme}")
    if hook:
        prefs.append(f"Campaign hook: {hook}")
    if tone:
        prefs.append(f"Tone: {tone}")
    if party_level:
        prefs.append(f"Party level: {party_level}")
    prefs_block = "\n".join(prefs) if prefs else "Theme: (not specified)"

    if not guidelines:
        guidelines = (
            "- 3-4 sessions of play\n"
            "- Branching choices, concrete encounters\n"
            "- Ground NPCs and locations in the book excerpts below"
        )

    return f"""You are an expert RPG campaign designer.

BOOK CONTEXT (excerpts from the user's rulebook — use these as primary source material):
{book_block}
{sheets_block}
CAMPAIGN REQUEST:
{prefs_block}

SYSTEM RULES:
{system_block}

Create a COMPLETE, play-ready {complexity.upper()} campaign in {target_language}.
{guidelines}

{sections}

Ground the campaign in the book excerpts above. Use their terminology, setting, and tone.
Do not invent a generic fantasy world if the excerpts describe something specific.
Output in markdown. Language: {target_language}.
"""
