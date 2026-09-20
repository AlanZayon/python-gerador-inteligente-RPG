"""Deterministic mock LLM for GameMasterRuntime tests and offline play."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMTurn:
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    narration: str = ""
    speaker: str = "gm"
    voice_direction: Any | None = None


_SKILL_RE = re.compile(
    r"\b(climb|sneak|stealth|search|hide|persuade|athletics|perception|"
    r"check|lockpick|jump|roll|d20|d6)\b",
    re.I,
)


class MockGMLLM:
    """Scripted tool-using GM. Never invents dice totals — always uses tools."""

    def complete_turn(self, context: dict) -> LLMTurn:
        action = (context.get("player_action") or "").strip()
        lower = action.lower()
        character_id = context.get("actor_character_id")
        state = context.get("campaign_state") or {}
        purpose = context.get("purpose") or "gm_turn"

        if purpose == "roll_resolution":
            result = context.get("resolved_roll") or state.get("last_dice") or {}
            total = result.get("total")
            skill = result.get("skill") or "check"
            success = result.get("success")
            if success is True:
                outcome = "success"
            elif success is False:
                outcome = "failure"
            else:
                outcome = "the result"
            return LLMTurn(
                tool_calls=[],
                narration=f"The {skill} check is {outcome}. The dice settle on {total}.",
            )

        if lower.startswith("gm_script:voice"):
            from services.voice.models import VoiceDirection

            return LLMTurn(
                tool_calls=[
                    {
                        "name": "update_world_state",
                        "args": {"patch": {"notes": ["voice script"]}},
                    }
                ],
                narration="A porta começa a se abrir lentamente...",
                speaker="gm",
                voice_direction=VoiceDirection(tags=["[slowly]", "[whispers]"]),
            )

        if lower.startswith("gm_script:hidden_roll"):
            notation = "1d20"
            m = re.search(r"(\d*)d(\d+)", lower)
            if m:
                notation = f"{m.group(1) or '1'}d{m.group(2)}"
            return LLMTurn(
                tool_calls=[
                    {
                        "name": "roll_dice",
                        "args": {"notation": notation, "reason": "hidden GM roll"},
                    }
                ],
                narration="",
            )

        if lower.startswith("gm_script:"):
            return self._scripted(action, character_id)

        if purpose == "session_opening" or lower.startswith("system:session_opening"):
            from services.play.gm.opening_brief import build_opening_brief

            blueprint = context.get("blueprint") or {}
            brief = context.get("opening_brief") or build_opening_brief(blueprint)
            title = (brief.get("title") or blueprint.get("title") or "the adventure").strip()
            overview = (
                brief.get("overview")
                or blueprint.get("premise")
                or "Trouble gathers at the edge of the map."
            ).strip()
            start_hook = (brief.get("start_hook") or overview).strip()
            party = context.get("party") or []
            names = ", ".join(p.get("name") for p in party if p.get("name")) or "the party"
            blob = f"{title} {overview} {start_hook}".lower()
            location = "the salt docks" if "salt" in blob else "the threshold"
            return LLMTurn(
                tool_calls=[
                    {
                        "name": "update_world_state",
                        "args": {
                            "patch": {
                                "scene": f"Opening of {title}",
                                "location": location,
                                "notes": [overview[:160], start_hook[:160]],
                            }
                        },
                    }
                ],
                narration=(
                    f"Overview — {title}. {overview} "
                    f"Starting hook: {names} face this now — {start_hook} "
                    "The next move is yours."
                ),
            )

        if _SKILL_RE.search(lower) and not state.get("pending_check"):
            return LLMTurn(
                tool_calls=[
                    {
                        "name": "lookup_rules",
                        "args": {"query": action[:200]},
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

    def continue_with_tools(self, context: dict, tool_results: list[dict]) -> LLMTurn:
        if context.get("purpose") == "roll_resolution":
            return self.complete_turn(context)
        if any(tr.get("name") == "lookup_rules" for tr in (tool_results or [])):
            action = (context.get("player_action") or "").strip()
            skill = "Athletics"
            m = re.search(r"for ([A-Za-z]+)", action, re.I)
            if m:
                skill = m.group(1)
            elif re.search(r"climb", action, re.I):
                skill = "Athletics"
            elif re.search(r"search|perception", action, re.I):
                skill = "Perception"
            elif re.search(r"sneak|stealth|hide", action, re.I):
                skill = "Stealth"
            notation = "1d20"
            m_dice = re.search(r"(\d*)d(\d+)", action.lower())
            if m_dice:
                notation = f"{m_dice.group(1) or '1'}d{m_dice.group(2)}"
            return LLMTurn(
                tool_calls=[
                    {
                        "name": "request_roll",
                        "args": {
                            "character_id": context.get("actor_character_id"),
                            "skill": skill,
                            "notation": notation,
                            "dc": 12,
                            "reason": action,
                            "success_rule": "meet_or_beat",
                        },
                    }
                ],
                narration="",
            )
        return LLMTurn(tool_calls=[], narration=context.get("pending_narration") or "")

    def narrate_after_tools(self, context: dict, tool_results: list[dict]) -> str:
        for tr in tool_results:
            if tr["name"] == "request_roll" and tr["result"].get("ok"):
                pending = tr["result"]["result"]
                skill = pending.get("skill") or "check"
                notation = pending.get("notation") or "dice"
                dc = pending.get("dc")
                who = (context.get("character_name") or "").strip() or "You"
                dice = f" ({notation})" if notation else ""
                dc_bit = f" against DC {dc}" if dc is not None else ""
                return f"{who}, make a {skill} check{dice}{dc_bit}."
            if tr["name"] == "roll_dice" and tr["result"].get("ok"):
                total = tr["result"]["result"]["total"]
                return f"The dice settle on {total}."
            if tr["name"] == "perform_check" and tr["result"].get("ok"):
                total = tr["result"]["result"]["total"]
                skill = tr["result"]["result"].get("skill")
                return f"Your {skill} check totals {total}."
            if tr["name"] == "confirm_roll" and tr["result"].get("ok"):
                total = tr["result"]["result"]["total"]
                skill = tr["result"]["result"].get("skill") or "check"
                return f"The {skill} check settles on {total}."
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
