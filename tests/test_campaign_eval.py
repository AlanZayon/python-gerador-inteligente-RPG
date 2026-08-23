"""Tests for the campaign quality rubric."""

from services.campaign_eval import evaluate_rubric


RICH = """
# Salt on the Throne

## Overview
Valdris is drowning. The Sahuagin Court, the harbor guild, and the tide priests
all want the last dry street. The stake is the city's remaining children.
The theme is what you will trade for dry land. The conflict escalates each night
as the flood clock advances.

## Starting Hook
Captain Mira hauls a salt-stained sigil onto the table and asks whether you
warn the court or bury the proof. If the players refuse, the sluice opens at dawn.

## Session 1: Harbor Watch
**Objectives:**
- Interrogate the envoy without starting a riot
- Find three independent clues to who opened the gate

### Scene: Docks
Talk, sneak, or force your way past the watch. DC 14 Insight or a 3d6 skill roll.
If they fail, the Flood clock ticks and the low quarter floods.
If the players ally with Mira, the guild owes them a boat.
Alternatively they may sell her out to the priests.

## Session 2: Court of Salt
Consequence of session 1 determines who holds the gate keys.

## Important NPCs
### Captain Mira
**Role:** Harbor captain
Want: keep her crews breathing. Secret: she opened the first vent to buy time.
### Tide Priest
**Role:** priest
Want: drown the guild. Secret: he bargains with the Sahuagin Envoy.
### Sahuagin Envoy
**Role:** antagonist
Want: the dry street as tribute.
### Dock Rat
**Role:** informant

## Enemies and Creatures
Sahuagin raiding parties and guild enforcers.

## Campaign Challenges and Puzzles
Three clues: sigil, priest ledger, salt in the envoy's gills.
Clocks: Flood, Honor, Riot.

## Possible Endings
- If they open the sluice: the low quarter drowns, Mira lives.
- If they hold the gate: the court burns the docks.

## Maps and Locations
Valdris Docks reek of tar. The Court of Salt echoes.

## Rewards
Harbor key, guild debt, a named relic from the book.
"""

THIN = """
# Adventure
## Overview
You meet in a tavern. An ancient evil stirs. A mysterious stranger hires you.
The dark lord waits in forgotten ruins.
## Session 1
Go to the dungeon and fight.
"""


def test_rich_campaign_outscores_generic_tavern():
    rich = evaluate_rubric(RICH, complexity="simples", key_terms=["Valdris", "Sahuagin"])
    thin = evaluate_rubric(THIN, complexity="simples", key_terms=["Valdris", "Sahuagin"])
    assert rich["overall"] > thin["overall"]
    assert rich["scores"]["gameplay"] > thin["scores"]["gameplay"]
    assert rich["scores"]["npcs"] > thin["scores"]["npcs"]


def test_rich_campaign_meets_simple_threshold():
    rich = evaluate_rubric(
        RICH,
        complexity="simples",
        key_terms=["Valdris", "Sahuagin"],
        state={
            "npcs": [{"name": "Captain Mira"}, {"name": "Tide Priest"}, {"name": "Sahuagin Envoy"}, {"name": "Dock Rat"}],
            "factions": [{"name": "Harbor guild"}, {"name": "Sahuagin Court"}],
            "locations": [{"name": "Valdris Docks"}, {"name": "Court of Salt"}, {"name": "Low quarter"}],
            "fronts": [{"name": "Flood"}],
            "grounded_terms": ["Valdris", "Sahuagin"],
        },
    )
    assert rich["overall"] >= 7.0
    assert rich["session_count"] >= 1


def test_rubric_accepts_string_names_in_state():
    result = evaluate_rubric(
        RICH,
        complexity="simples",
        key_terms=["Valdris"],
        state={
            "npcs": ["Captain Mira", "Tide Priest", "Sahuagin Envoy", "Dock Rat"],
            "factions": ["Harbor guild", "Sahuagin Court"],
            "locations": ["Valdris Docks", "Court of Salt", "Low quarter"],
            "fronts": ["Flood"],
            "grounded_terms": ["Valdris"],
        },
    )
    assert result["overall"] > 0
    assert result["scores"]["consistency"] >= 6.0


def test_parenthetical_names_count_as_present():
    text = RICH.replace("Captain Mira", "Mira")
    result = evaluate_rubric(
        text,
        complexity="simples",
        key_terms=["Valdris"],
        state={
            "npcs": ["Mira (harbor captain)", "Tide Priest", "Sahuagin Envoy", "Dock Rat"],
            "factions": ["Harbor guild", "Sahuagin Court"],
            "locations": ["Valdris Docks", "Court of Salt", "Low quarter"],
            "fronts": ["Flood"],
            "grounded_terms": ["Valdris"],
        },
    )
    assert result["scores"]["consistency"] >= 6.0
