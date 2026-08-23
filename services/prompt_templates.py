"""Campaign generation prompt templates by RPG system."""

from services.campaign_quality import quality_requirements, word_count

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
    "gurps": """
- Use GURPS Lite: ST/DX/IQ/HT, skills, advantages/disadvantages, 3d6 roll-under
- Quote specific skill names and modifiers; mention character-point costs when relevant
- Do not assume dungeon fantasy; match the book's genre
- Combat is lethal; social and investigative scenes must be equally playable
""",
    "blood_honor": """
- Center clan, honor, court, and personal obligation — not dungeon crawls
- Conflicts should be social and political first; violence is rare, named, and costly
- Reuse the book's procedures (risks, aspects, gifts, clan holdings) instead of D&D-style DCs
- Tragedy means choices have irreversible social consequences
""",
    "fragged": """
- Keep a post-collapse science-fiction identity: remnant corporations, modified cultures, resources
- Use the book's procedures (resources, spare time, influence, spacecraft) rather than medieval fantasy tropes
- Faction politics and scarcity drive play more than monster-of-the-week
- Do not reskin knights and dungeons as spaceships
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
    requirements = quality_requirements(complexity, target_language)

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
{requirements}
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
{requirements}

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
{requirements}

{sections}

{grounding}
Use markdown. Language: {target_language}.
"""


def build_expand_retry_prompt(
    content: str,
    issues: list[str],
    target_language: str,
    key_terms: list[str] | None = None,
    complexity: str = "mediana",
) -> str:
    issue_list = "\n".join(f"- {i}" for i in issues)
    terms_note = ""
    if key_terms:
        terms_note = (
            "\nWeave in these proper names from the source book: "
            + ", ".join(key_terms[:10])
            + "\n"
        )
    requirements = quality_requirements(complexity, target_language)
    draft_words = word_count(content)
    return f"""Rewrite the COMPLETE play-ready RPG campaign in {target_language}.
Do not return a summary, a patch, or a list of changes. Output the full markdown campaign.
The draft below is {draft_words} words. Your rewrite MUST be at least {draft_words} words.
Never replace a long campaign with a short outline.

Fix these issues:
{issue_list}
{terms_note}
{requirements}

Keep useful content from the draft below and expand it until every requirement is met.

DRAFT:
{content[:80000]}
"""


def build_plan_prompt(
    *,
    book_context: str,
    target_language: str,
    complexity: str,
    guidelines: str,
    system_preset: str | None,
    party_level: str = "",
    tone: str = "",
    theme: str = "",
    character_sheets: str = "",
    json_instructions: str = "",
) -> str:
    from services.campaign_schema import PLAN_JSON_INSTRUCTIONS, spec_for

    spec = spec_for(complexity)
    system_block = get_system_instructions(system_preset)
    prefs = []
    if party_level:
        prefs.append(f"Party level: {party_level}")
    if tone:
        prefs.append(f"Tone: {tone}")
    if theme:
        prefs.append(f"Theme/hook: {theme}")
    prefs_block = "\n".join(prefs)
    sheets_block = f"\nPLAYER CHARACTERS:\n{character_sheets}\n" if character_sheets else ""
    schema = json_instructions or PLAN_JSON_INSTRUCTIONS
    return f"""You are a senior RPG campaign planner. Do NOT write the playable manuscript yet.
Build a structured plan that later writers will expand. Invent nothing that contradicts the book excerpts.
If the excerpts describe a specific setting, reuse its names. If they are mostly rules, invent a setting that obeys those rules.

BOOK EXCERPTS:
{book_context}
{sheets_block}
SYSTEM:
{system_block}
{prefs_block}

COMPLEXITY: {complexity}
{guidelines}
Depth target: {spec['description']}
Minimums: sessions {spec['sessions'][0]}+, NPCs {spec['min_npcs']}+, factions {spec['min_factions']}+, locations {spec['min_locations']}+, fronts {spec['min_fronts']}+, endings {spec['min_endings']}+.

Rules:
- Every NPC has a want, a secret, and a tie to the conflict.
- Every scene lists at least two approaches and a failure consequence.
- Mysteries include at least three independent clues when complexity is mediana or complexa.
- grounded_terms must be copied verbatim from the excerpts when names exist.
- Output language for string values: {target_language}.

{schema}
"""


def build_overview_prompt(
    *,
    digest: str,
    book_context: str,
    target_language: str,
    system_preset: str | None,
    overview_label: str,
    hook_label: str,
) -> str:
    system_block = get_system_instructions(system_preset)
    return f"""You are writing the opening of a play-ready RPG campaign for a GM.
Use ONLY names from the campaign state. Do not rename anyone.

CAMPAIGN STATE:
{digest}

SYSTEM:
{system_block}

BOOK EXCERPTS (grounding):
{book_context[:6000]}

Write markdown with exactly these headings and no others:
# {{title from state}}
## {overview_label}
## {hook_label}

Overview: premise, thematic question, central conflict, stakes, faction pressures, how the campaign escalates.
Starting hook: a situation already in motion, what the PCs see, a first choice.
Language: {target_language}. No code fences.
"""


def build_session_prompt(
    *,
    digest: str,
    session_json: str,
    previous_summary: str,
    extra_context: str,
    target_language: str,
    system_preset: str | None,
    session_label: str,
    objectives_label: str,
) -> str:
    system_block = get_system_instructions(system_preset)
    extra = extra_context.strip() or "(no extra excerpts)"
    prev = previous_summary.strip() or "(this is the opening session)"
    return f"""You are writing ONE playable session for a GM. Expand the session brief; do not invent a new plot.

CAMPAIGN STATE (continuity bible):
{digest}

THIS SESSION BRIEF:
{session_json}

PREVIOUS SESSIONS:
{prev}

EXTRA BOOK EXCERPTS:
{extra}

SYSTEM:
{system_block}

Write markdown starting with:
## {session_label} {{number}}: {{title}}

Include:
- **{objectives_label}:** bullet list
- Scenes as ### headings. Each scene: what is happening, who is present, at least two approaches, failure consequences, and any clue found here.
- A boxed GM note with a check/DC or system procedure from the book.
- An explicit branch: If the players do A... / If they do B...
- How this session advances a front.

Reuse names exactly. Language: {target_language}. No code fences. No other H2 headings.
"""


def build_support_prompt(
    *,
    digest: str,
    book_context: str,
    target_language: str,
    system_preset: str | None,
    labels: dict[str, str],
) -> str:
    system_block = get_system_instructions(system_preset)
    return f"""You are writing the reference appendix of a play-ready RPG campaign.
Use ONLY names from the campaign state.

CAMPAIGN STATE:
{digest}

SYSTEM:
{system_block}

BOOK EXCERPTS:
{book_context[:5000]}

Write markdown with these H2 headings in this order (and no extra H2s):
## {labels['npcs']}
## {labels['enemies']}
## {labels['puzzles']}
## {labels['endings']}
## {labels['maps']}
## {labels['rewards']}

NPCs: ### Name, **Role**, want, secret, tell, relationship, how they act if pressured.
Enemies: factions and opposition as usable GM tools, not generic stat spam.
Challenges: clocks, mysteries, three-clue paths, social/stealth/force options.
Endings: one subsection per planned ending with the condition that produces it.
Maps: sensory locations and how they connect.
Rewards: diegetic, useful, tied to choices.
Language: {target_language}. No code fences.
"""


def build_revise_prompt(
    *,
    digest: str,
    section_heading: str,
    section_body: str,
    issues: list[str],
    target_language: str,
    system_preset: str | None,
) -> str:
    system_block = get_system_instructions(system_preset)
    issue_list = "\n".join(f"- {i}" for i in issues) or "- Add specific, playable detail"
    return f"""Revise ONLY this campaign section. Keep the heading. Keep every established name.
Do not rewrite the rest of the campaign.

CAMPAIGN STATE:
{digest}

SYSTEM:
{system_block}

ISSUES TO FIX:
{issue_list}

SECTION:
## {section_heading}
{section_body}

Return the full revised section including the H2 heading. Language: {target_language}. No code fences.
"""

