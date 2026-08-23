"""Tests for hierarchical campaign pipeline with a fake LLM."""

import json

from services.campaign_pipeline import generate_campaign_markdown
from tests.test_campaign_schema import _min_plan


def test_pipeline_falls_back_when_plan_is_not_json():
    markdown, meta = generate_campaign_markdown(
        book_context="The city of Valdris drowns beneath the Sahuagin Court.",
        key_terms=["Valdris", "Sahuagin"],
        target_language="en",
        complexity="simples",
        guidelines="short",
        system_preset="generic",
        llm_fn=lambda prompt: "# Overview\nSession 1\nReady. Valdris.",
        fallback_full_prompt="# Overview\nBOOK CONTEXT Valdris\nSession 1\nReady.",
    )
    assert meta["pipeline"] == "fallback-full"
    assert "Valdris" in markdown or "Overview" in markdown


def test_pipeline_writes_from_valid_plan():
    plan = _min_plan("simples")
    calls = {"n": 0}

    def llm(prompt: str) -> str:
        calls["n"] += 1
        if "valid JSON" in prompt or "ONLY valid JSON" in prompt or "structured plan" in prompt.lower() or "senior RPG campaign planner" in prompt:
            return json.dumps(plan)
        if "opening of a play-ready" in prompt or "exactly these headings" in prompt:
            return "# Salt on the Throne\n## Overview\nValdris drowns.\n## Starting Hook\nMira slams the sigil down."
        if "ONE playable session" in prompt or "THIS SESSION BRIEF" in prompt:
            return "## Session 1: Harbor Watch\n**Objectives:** Survive.\nIf the players talk, Mira helps. If they fail, the sluice opens."
        if "reference appendix" in prompt or "Important NPCs" in prompt or "write the reference" in prompt.lower():
            return (
                "## Important NPCs\n### Captain Mira\nWant: crews live. Secret: she opened a vent.\n"
                "## Enemies and Creatures\nSahuagin\n"
                "## Campaign Challenges and Puzzles\nThree clues.\n"
                "## Possible Endings\nTwo endings.\n"
                "## Maps and Locations\nValdris Docks.\n"
                "## Rewards\nHarbor key."
            )
        if "Revise ONLY" in prompt:
            return "## Overview\nRevised: Valdris still drowns, but Mira names the envoy."
        return "# Salt\n## Overview\nValdris"

    markdown, meta = generate_campaign_markdown(
        book_context="Valdris and the Sahuagin Court contest the last dry street.",
        key_terms=["Valdris", "Sahuagin"],
        target_language="en",
        complexity="simples",
        guidelines="short",
        system_preset="generic",
        llm_fn=llm,
        fallback_full_prompt="# unused",
    )
    assert meta["plan_used"] is True
    assert "Salt" in markdown or "Valdris" in markdown
    assert calls["n"] >= 3
