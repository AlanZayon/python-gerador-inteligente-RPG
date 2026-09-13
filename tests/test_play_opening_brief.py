"""Opening brief: overview + start hook from campaign material."""

from services.play.gm.opening_brief import build_opening_brief


def test_brief_prefers_manuscript_overview_and_hook():
    blueprint = {
        "title": "Salt on the Throne",
        "premise": "Blueprint premise that should be ignored when manuscript exists.",
    }
    manuscript = """# Salt on the Throne

## Overview
The coast is ruled by salt merchants who buy silence. A stolen charter threatens every dock.

## Starting Hook
At dawn the party finds the harbormaster's seal broken on a crate marked for the palace.
"""
    brief = build_opening_brief(blueprint, manuscript)
    assert brief["title"] == "Salt on the Throne"
    assert "salt merchants" in brief["overview"].lower()
    assert "harbormaster" in brief["start_hook"].lower()
    assert "Blueprint premise" not in brief["overview"]


def test_brief_falls_back_to_blueprint_when_no_manuscript():
    blueprint = {
        "title": "Echoes",
        "premise": "Storms gather over the salt flats and old debts come due.",
        "central_conflict": "Smugglers versus the crown's tax collectors.",
        "stakes": "Whoever controls the flats controls the winter grain.",
        "tone": "gritty",
        "sessions": [
            {
                "number": 1,
                "title": "Broken Seal",
                "dramatic_function": "hook",
                "scenes": [
                    {
                        "name": "The Dockyard",
                        "location": "South pier",
                        "purpose": "Discover the broken seal and choose who to trust",
                    }
                ],
            }
        ],
    }
    brief = build_opening_brief(blueprint)
    assert "Storms gather" in brief["overview"]
    assert "Smugglers" in brief["overview"]
    assert "Dockyard" in brief["start_hook"] or "South pier" in brief["start_hook"]
    assert "broken seal" in brief["start_hook"].lower()
    assert len(brief["overview"]) <= 520
    assert len(brief["start_hook"]) <= 420


def test_brief_clips_long_manuscript_sections():
    long_overview = "Word. " * 200
    long_hook = "Hook sentence that keeps going. " * 80
    manuscript = f"## Overview\n{long_overview}\n\n## Starting Hook\n{long_hook}\n"
    brief = build_opening_brief({"title": "Long"}, manuscript)
    assert len(brief["overview"]) <= 520
    assert len(brief["start_hook"]) <= 420
    assert brief["overview"]
    assert brief["start_hook"]
