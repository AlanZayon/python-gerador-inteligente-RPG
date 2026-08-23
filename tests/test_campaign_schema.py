"""Tests for campaign plan schema and JSON parsing."""

from services.campaign_schema import (
    PLAN_JSON_INSTRUCTIONS,
    canonical_complexity,
    name_registry,
    normalize_plan,
    parse_json_object,
    plan_is_structurally_complete,
    spec_for,
    state_digest,
)


def _min_plan(complexity: str = "simples") -> dict:
    spec = spec_for(complexity)
    lo, _hi = spec["sessions"]
    sessions = []
    for i in range(lo):
        sessions.append(
            {
                "number": i + 1,
                "title": f"Session {i + 1} tide",
                "dramatic_function": "hook" if i == 0 else "escalation",
                "objectives": ["Stop the floodgate sabotage"],
                "scenes": [
                    {
                        "name": "Harbor watch",
                        "purpose": "pressure",
                        "location": "Valdris Docks",
                        "npcs": ["Captain Mira"],
                        "approaches": ["talk", "sneak", "force"],
                        "failure": "The sluice opens at dawn",
                    }
                ],
                "choices": [
                    {"decision": "Warn the court?", "if_a": "Open hunt", "if_b": "Quiet alliance"},
                    {"decision": "Open the sluice now?", "if_a": "Flood the low quarter", "if_b": "Hold the gate"},
                ],
                "clues_planted": ["Salt-stained sigil"],
                "clock_advance": "Flood clock ticks",
                "rewards": ["Harbor key"],
            }
        )
    npcs = [
        {
            "name": n,
            "role": "role",
            "want": "want",
            "secret": "secret",
            "tie": "tie",
            "quirk": "quirk",
            "attitude": "neutral",
        }
        for n in ["Captain Mira", "Tide Priest", "Sahuagin Envoy", "Dock Rat"][: spec["min_npcs"]]
    ]
    while len(npcs) < spec["min_npcs"]:
        npcs.append({**npcs[0], "name": f"NPC {len(npcs)}"})
    factions = [
        {"name": f"Faction {i}", "want": "w", "method": "m", "pressure": "p", "why_pcs_care": "c"}
        for i in range(spec["min_factions"])
    ]
    locations = [
        {"name": f"Place {i}", "function": "f", "senses": "s", "links": []}
        for i in range(spec["min_locations"])
    ]
    fronts = [
        {"name": f"Front {i}", "impulse": "i", "portents": ["a", "b"], "doom": "d"}
        for i in range(spec["min_fronts"])
    ]
    mysteries = []
    for i in range(spec["min_mysteries"]):
        mysteries.append(
            {
                "question": f"Who opened the gate {i}?",
                "truth": "The envoy",
                "clues": [
                    {"clue": "c1", "source": "dock"},
                    {"clue": "c2", "source": "priest"},
                    {"clue": "c3", "source": "sigil"},
                ],
            }
        )
    endings = [
        {"condition": f"cond {i}", "outcome": f"out {i}"} for i in range(spec["min_endings"])
    ]
    return {
        "title": "Salt on the Throne",
        "premise": "Valdris is drowning and three powers race to own the last dry street.",
        "thematic_question": "What will you trade for dry land?",
        "tone": "briny political horror",
        "central_conflict": "Court vs Sahuagin vs smugglers",
        "stakes": "The city sinks in nine days",
        "themes": ["drowning", "betrayal"],
        "grounded_terms": ["Valdris", "Sahuagin"],
        "rules_to_use": ["ability checks"],
        "factions": factions,
        "npcs": npcs,
        "locations": locations,
        "fronts": fronts,
        "mysteries": mysteries,
        "sessions": sessions,
        "endings": endings,
        "secrets_gm": ["The priest opened the first sluice"],
    }


def test_canonical_complexity_aliases():
    assert canonical_complexity("simple") == "simples"
    assert canonical_complexity("COMPLEX") == "complexa"


def test_parse_json_object_strips_fences():
    raw = "```json\n{\"title\": \"X\", \"premise\": \"" + ("word " * 20) + "\"}\n```"
    parsed = parse_json_object(raw)
    assert parsed and parsed["title"] == "X"


def test_normalize_and_complete_simple_plan():
    raw = _min_plan("simples")
    state = normalize_plan(raw, "simples")
    assert state is not None
    ok, issues = plan_is_structurally_complete(state, "simples")
    assert ok, issues
    digest = state_digest(state)
    assert "Valdris" in digest
    assert "Captain Mira" in digest
    names = name_registry(state)
    assert "Captain Mira" in names["npcs"]


def test_thin_plan_is_rejected():
    state = normalize_plan({"title": "Hi", "premise": "Too short"}, "mediana")
    assert state is None


def test_plan_instructions_are_json():
    assert '"title"' in PLAN_JSON_INSTRUCTIONS
    assert spec_for("complexa")["min_factions"] >= 4


def test_normalize_fills_string_choices_and_named_lists():
    raw = _min_plan("simples")
    raw["npcs"] = ["Captain Mira", "Tide Priest", "Sahuagin Envoy", "Dock Rat"]
    raw["factions"] = ["Harbor guild", "Sahuagin Court"]
    raw["sessions"][0]["choices"] = ["Warn the court?", "Open the sluice now?"]
    raw["sessions"][0]["scenes"][0]["approaches"] = ["talk"]
    state = normalize_plan(raw, "simples")
    assert state is not None
    assert state["npcs"][0]["name"] == "Captain Mira"
    assert len(state["sessions"][0]["choices"]) >= 2
    assert len(state["sessions"][0]["scenes"][0]["approaches"]) >= 2
    ok, issues = plan_is_structurally_complete(state, "simples")
    assert ok, issues


def test_normalize_strips_parenthetical_titles():
    raw = _min_plan("simples")
    raw["npcs"][0]["name"] = "Captain Mira (harbor captain)"
    raw["factions"][0]["name"] = "Harbor guild (smugglers)"
    state = normalize_plan(raw, "simples")
    assert state["npcs"][0]["name"] == "Captain Mira"
    assert state["factions"][0]["name"] == "Harbor guild"
