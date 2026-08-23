"""Campaign generation prompt templates by RPG system."""

SYSTEM_SECTIONS = {
    "generic": """
- Use system-agnostic fantasy terminology
- Reference ability checks and difficulty classes without brand names
""",
    "dnd5e": """
- Use D&D 5e conventions: ability checks, DCs, short/long rests, CR-appropriate encounters
- Include XP or milestone leveling notes
- Stat blocks: AC, HP, attack bonus, save DCs
""",
    "pf2e": """
- Use Pathfinder 2e three-action economy and proficiency tiers (+8/+10/+12 etc.)
- Reference level-based DCs and creature level
- Include Recall Knowledge and exploration mode where relevant
""",
    "coc": """
- Use Call of Cthulhu: Sanity checks, skill percentiles, investigation focus
- Clues must be discoverable; avoid combat-only solutions
- Tone: creeping dread, 1920s–modern era as appropriate
""",
}


def get_system_instructions(preset_id: str | None) -> str:
    return SYSTEM_SECTIONS.get(preset_id or "generic", SYSTEM_SECTIONS["generic"])


def _mandatory_sections(character_sheets: str = "") -> str:
    if character_sheets:
        return (
            "Mandatory sections: OVERVIEW, STARTING HOOK, DETAILED SESSIONS "
            "(each with objectives, encounters, NPCs, treasures — reference each PC by name), "
            "IMPORTANT NPCS, ENEMIES AND CREATURES, REWARDS, CHALLENGES AND PUZZLES, "
            "POSSIBLE ENDINGS, MAPS AND LOCATIONS.\n\n"
            "Tailor hooks, encounters, and rewards to these PLAYER CHARACTERS. "
            "Replace generic archetypes with personalized plot threads for these characters."
        )
    return (
        "Mandatory sections: OVERVIEW, STARTING HOOK, CHARACTER ARCHETYPES, DETAILED SESSIONS, "
        "IMPORTANT NPCS, ENEMIES AND CREATURES, REWARDS, CHALLENGES AND PUZZLES, "
        "POSSIBLE ENDINGS, MAPS AND LOCATIONS."
    )


def build_campaign_prompt(
    *,
    book_bible: dict | None = None,
    book_context: str = "",
    target_language: str,
    complexity: str,
    guidelines: str,
    system_preset: str | None,
    party_level: str = "",
    tone: str = "",
    theme: str = "",
    pass_type: str = "full",
    outline: str = "",
    character_sheets: str = "",
) -> str:
    system_block = get_system_instructions(system_preset)
    prefs = ""
    if party_level:
        prefs += f"\nParty level: {party_level}"
    if tone:
        prefs += f"\nTone: {tone}"
    if theme:
        prefs += f"\nOptional theme/hook: {theme}"

    context_block = (book_context or "").strip() or str(book_bible or {})[:12000]
    grounding = (
        "Ground the campaign in the book's setting, terminology, and mechanics "
        "from the excerpts above. Reuse named places, factions, and terms verbatim. "
        "Do not invent a generic fantasy world if the excerpts describe something specific."
    )
    sections = _mandatory_sections(character_sheets)
    sheets_block = f"\n\n{character_sheets}\n" if character_sheets else ""

    if pass_type == "outline":
        outline_note = ""
        if character_sheets:
            outline_note = "\nInclude personalized hooks for each player character listed below."
        return f"""You are an expert RPG campaign designer.

BOOK CONTEXT (excerpts from the user's uploaded rulebook):
{context_block}
{sheets_block}
SYSTEM RULES:
{system_block}
{prefs}

Create a detailed campaign OUTLINE for a {complexity.upper()} campaign in {target_language}.
{guidelines}
{outline_note}

{grounding}

Include: title, overview, starting hook, session-by-session bullet outline, key NPCs list, major locations.
Output in markdown. Language: {target_language}.
"""

    if pass_type == "expand" and outline:
        return f"""You are an expert RPG campaign designer.

BOOK CONTEXT (excerpts from the user's uploaded rulebook):
{context_block}
{sheets_block}
SYSTEM RULES:
{system_block}
{prefs}

Expand this outline into a COMPLETE, play-ready campaign in {target_language}:
{guidelines}

OUTLINE TO EXPAND:
{outline}

{sections}

{grounding}
Use markdown. Be specific and table-ready. Language: {target_language}.
"""

    return f"""You are an expert RPG campaign designer.

BOOK CONTEXT (excerpts from the user's uploaded rulebook):
{context_block}
{sheets_block}
SYSTEM RULES:
{system_block}
{prefs}

Create a COMPLETE, play-ready {complexity.upper()} campaign in {target_language}.
{guidelines}

{sections}

{grounding}
Use markdown. Language: {target_language}.
"""


def build_expand_retry_prompt(
    content: str,
    issues: list[str],
    target_language: str,
    key_terms: list[str] | None = None,
) -> str:
    issue_list = "\n".join(f"- {i}" for i in issues)
    terms_note = ""
    if key_terms:
        terms_note = (
            "\nWeave in these terms from the source book: "
            + ", ".join(key_terms[:10])
            + "\n"
        )
    return f"""Improve this RPG campaign draft. Fix these quality issues:
{issue_list}
{terms_note}
Expand missing sections. Target language: {target_language}.
Reuse names and mechanics from the source book; do not replace them with generic fantasy.

DRAFT:
{content[:25000]}
"""
