"""Tests for campaign markdown normalizer."""

from pathlib import Path

from services.campaign_normalize import extract_campaign_title, normalize_campaign_markdown
from services.campaign_parse import parse_campaign
from tasks.campaign_tasks import format_campaign_output


MESSY = """```markdown
# RPG Campaign — MEDIUM

**Duration**: 3-4 sessions
**Language**: en

## Inspired by your book
- Setting
- Excerpt

---

# The Shattered Oath: A Campaign of Broken Covenants

# Overview
A sacred pact has fractured.

## Starting Hook: The Fracture
The sky splits.

## Session 1: Gathering Storm
**Session Objectives:**
- Meet the council

### **Encounter 1A: The Council (Roleplay)**
Sister Meridith speaks.

## Session 4 (Optional): Echoes and Aftermath
Optional epilogue.

## Important NPCs
### Sister Meridith
**Role:** Temple representative
```
"""


def test_extract_title_skips_wrapper():
    assert extract_campaign_title(MESSY) == "The Shattered Oath: A Campaign of Broken Covenants"


def test_normalize_drops_wrapper_and_inspired():
    out = normalize_campaign_markdown(MESSY)
    assert out.startswith("# The Shattered Oath: A Campaign of Broken Covenants")
    assert "RPG Campaign" not in out
    assert "## Inspired" not in out
    assert "Setting" not in out
    assert "## Overview" in out
    assert "## Session 1: Gathering Storm" in out
    assert "## Session 4 (Optional): Echoes and Aftermath" in out
    assert "### Encounter 1A: The Council (Roleplay)" in out
    assert "### **Encounter" not in out
    assert out.count("# The Shattered Oath") == 1


def test_normalize_demotes_section_h1():
    out = normalize_campaign_markdown("# Cool Title\n\n# Overview\nHello\n")
    assert out.startswith("# Cool Title")
    assert "## Overview" in out
    assert "\n# Overview" not in out


def test_format_campaign_output_single_title():
    formatted = format_campaign_output(
        "# The Shattered Oath\n\n## Overview\nA pact breaks.\n\n## Session 1: Storm\nGo.\n",
        "mediana",
        "en",
    )
    assert formatted.startswith("# The Shattered Oath")
    assert "RPG Campaign" not in formatted
    assert formatted.count("# The Shattered Oath") == 1
    assert "Generated from your uploaded rulebook" in formatted


def test_normalize_real_generated_campaign():
    path = Path.home() / "Downloads" / "rpg-campaign-medium.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    out = normalize_campaign_markdown(text)
    assert out.startswith("# The Shattered Oath")
    assert "## Overview" in out
    assert "## Session 1: Gathering Storm" in out
    assert "Visão Geral" not in out
    parsed = parse_campaign(out)
    assert "The Shattered Oath" in parsed["title"]
    types = [s["type"] for s in parsed["sections"]]
    assert types.count("session") >= 3
    assert "overview" in types
    assert "npcs" in types
    overview = next(s for s in parsed["sections"] if s["type"] == "overview")
    assert overview["heading"] == "Overview"


def test_normalize_portuguese_headings_when_language_is_pt():
    out = normalize_campaign_markdown(
        "# A Coroa Partida\n\n# Overview\nO reino fratura.\n\n## Session 1: Intriga\nGo.\n",
        language="pt",
    )
    assert "## Visão Geral" in out
    assert "## Sessão 1: Intriga" in out
