"""Deterministic mock LLM for GameMasterRuntime tests and offline play."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMTurn:
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    narration: str = ""


class MockGMLLM:
    """Scripted tool-using GM. Never invents dice totals — always uses tools."""

    def complete_turn(self, context: dict) -> LLMTurn:
        action = (context.get("player_action") or "").strip()
        lower = action.lower()
        character_id = context.get("actor_character_id")
        state = context.get("campaign_state") or {}

        if lower.startswith("gm_script:"):
            return self._scripted(action, character_id)

        if context.get("purpose") == "session_opening" or lower.startswith("system:session_opening"):
            blueprint = context.get("blueprint") or {}
            premise = (blueprint.get("premise") or "Trouble gathers at the edge of the map.").strip()
            title = (blueprint.get("title") or "the adventure").strip()
            party = context.get("party") or []
            names = ", ".join(p.get("name") for p in party if p.get("name")) or "the party"
            location = "the salt docks" if "salt" in premise.lower() or "salt" in title.lower() else "the threshold"
            return LLMTurn(
                tool_calls=[
                    {
                        "name": "update_world_state",
                        "args": {
                            "patch": {
                                "scene": f"Opening of {title}",
                                "location": location,
                                "notes": [premise[:160]],
                            }
                        },
                    }
                ],
                narration=(
                    f"{names} stand at {location}. {premise} "
                    "The air is tense; the next move is yours."
                ),
            )

        if "roll" in lower or "d20" in lower:
            notation = "1d20"
            m = re.search(r"(\d*)d(\d+)", lower)
            if m:
                notation = f"{m.group(1) or '1'}d{m.group(2)}"
            return LLMTurn(
                tool_calls=[
                    {
                        "name": "roll_dice",
                        "args": {"notation": notation, "reason": action},
                    }
                ],
                narration="",
            )

        if "check" in lower:
            skill = "Athletics"
            m = re.search(r"for ([A-Za-z]+)", action, re.I)
            if m:
                skill = m.group(1)
            return LLMTurn(
                tool_calls=[
                    {
                        "name": "perform_check",
                        "args": {"skill": skill, "modifier": 0},
                    }
                ],
                narration="",
            )

        location = state.get("location") or "the scene"
        return LLMTurn(
            tool_calls=[
                {
                    "name": "update_world_state",
                    "args": {
                        "patch": {
                            "notes": [f"Player acted: {action[:120]}"],
                            "scene": state.get("scene") or "In play",
                        }
                    },
                },
                {
                    "name": "create_event",
                    "args": {
                        "type": "player_action",
                        "payload": {"text": action},
                    },
                },
            ],
            narration=f"Around {location}, the table reacts as you: {action}",
        )

    def narrate_after_tools(self, context: dict, tool_results: list[dict]) -> str:
        for tr in tool_results:
            if tr["name"] == "roll_dice" and tr["result"].get("ok"):
                total = tr["result"]["result"]["total"]
                return f"The dice settle on {total}."
            if tr["name"] == "perform_check" and tr["result"].get("ok"):
                total = tr["result"]["result"]["total"]
                skill = tr["result"]["result"].get("skill")
                return f"Your {skill} check totals {total}."
        return context.get("pending_narration") or "The moment passes."

    def _scripted(self, action: str, character_id: str | None) -> LLMTurn:
        # "GM_SCRIPT: move to Harbor and set Mira hp to 7"
        location = "Harbor"
        m_loc = re.search(r"move to ([A-Za-z0-9_-]+)", action, re.I)
        if m_loc:
            location = m_loc.group(1).strip()
        hp = 7
        m_hp = re.search(r"hp to (\d+)", action, re.I)
        if m_hp:
            hp = int(m_hp.group(1))
        calls = [
            {
                "name": "update_world_state",
                "args": {"patch": {"location": location, "scene": location}},
            }
        ]
        if character_id:
            calls.append(
                {
                    "name": "update_character",
                    "args": {"character_id": character_id, "fields": {"hp": hp}},
                }
            )
        calls.append(
            {
                "name": "create_event",
                "args": {"type": "scripted", "payload": {"action": action}},
            }
        )
        return LLMTurn(
            tool_calls=calls,
            narration=f"You arrive at {location}.",
        )
