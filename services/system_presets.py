"""RPG system presets for campaign generation prompts."""

SYSTEM_PRESETS = {
    "generic": {
        "id": "generic",
        "name": "Generic Fantasy",
        "description": "System-agnostic fantasy adventure",
    },
    "dnd5e": {
        "id": "dnd5e",
        "name": "D&D 5e",
        "description": "Dungeons & Dragons 5th Edition terminology and encounter framing",
        "prompt_hint": "Use D&D 5e conventions: ability checks, DCs, short/long rests, CR-appropriate encounters.",
    },
    "pf2e": {
        "id": "pf2e",
        "name": "Pathfinder 2e",
        "description": "Pathfinder 2nd Edition three-action economy and proficiency ranks",
        "prompt_hint": "Use Pathfinder 2e conventions: three-action economy, proficiency tiers, level-based DCs.",
    },
    "coc": {
        "id": "coc",
        "name": "Call of Cthulhu",
        "description": "Investigation horror with Sanity and skill percentiles",
        "prompt_hint": "Use Call of Cthulhu tone: investigation, Sanity checks, creeping dread, 1920s–modern era.",
    },
    "gurps": {
        "id": "gurps",
        "name": "GURPS",
        "description": "Generic Universal RolePlaying System — point-buy, 3d6, genre-flexible",
        "prompt_hint": "Use GURPS Lite procedures: ST DX IQ HT, skills, advantages/disadvantages, 3d6 roll-under, character points. Do not default to dungeon fantasy unless the book or theme asks for it.",
    },
    "blood_honor": {
        "id": "blood_honor",
        "name": "Blood & Honor",
        "description": "Samurai tragedy: clan, honor, court, and costly violence",
        "prompt_hint": "Center clan politics, honor, gifts, and social risk. Violence is rare, personal, and expensive. Do not generate a dungeon crawl.",
    },
    "fragged": {
        "id": "fragged",
        "name": "Fragged Empire",
        "description": "Post-corporate science fiction: remnant cultures, resources, spacecraft",
        "prompt_hint": "Keep a distinct post-collapse science-fiction identity: corporations as ruins, modified cultures, resources, and spacecraft. Do not reskin medieval fantasy.",
    },
}


def get_preset(preset_id: str | None) -> dict:
    if not preset_id or preset_id not in SYSTEM_PRESETS:
        return SYSTEM_PRESETS["generic"]
    return SYSTEM_PRESETS[preset_id]


def preset_prompt_hint(preset_id: str | None) -> str:
    preset = get_preset(preset_id)
    return preset.get("prompt_hint", "")
