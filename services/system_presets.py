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
}


def get_preset(preset_id: str | None) -> dict:
    if not preset_id or preset_id not in SYSTEM_PRESETS:
        return SYSTEM_PRESETS["generic"]
    return SYSTEM_PRESETS[preset_id]


def preset_prompt_hint(preset_id: str | None) -> str:
    preset = get_preset(preset_id)
    return preset.get("prompt_hint", "")
