"""Live Game Master LLM via existing 9router chat completions + tools."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from services.llm_client import chat_completion, default_model
from services.play.gm.mock_llm import LLMTurn
from services.play.gm.tools import TOOL_NAMES, openai_tool_definitions
from services.voice.spoken import parse_spoken_content

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 3


def _safe_args(raw: Any) -> dict | None:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def validate_tool_calls(raw_calls: list[dict]) -> list[dict]:
    """Keep only known tools with object args."""
    validated: list[dict] = []
    for call in raw_calls or []:
        name = call.get("name") or ""
        if name not in TOOL_NAMES:
            logger.info("Skipping unknown GM tool: %s", name)
            continue
        args = _safe_args(call.get("args"))
        if args is None:
            logger.info("Skipping malformed GM tool args for %s", name)
            continue
        validated.append({"id": call.get("id"), "name": name, "args": args})
    return validated


def _assistant_message_with_tools(resp: dict, tool_calls: list[dict]) -> dict:
    message = dict(resp.get("message") or {})
    message.setdefault("role", "assistant")
    if tool_calls and not message.get("tool_calls"):
        message["tool_calls"] = [
            {
                "id": tc.get("id") or f"call_{i}",
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc.get("args") or {}, ensure_ascii=False),
                },
            }
            for i, tc in enumerate(tool_calls)
        ]
    return message


class LiveGMLLM:
    """9router-backed GM. Uses the same tool services as MockGMLLM."""

    def __init__(
        self,
        *,
        chat_fn: Callable[..., dict] | None = None,
        model: str | None = None,
    ):
        self._chat = chat_fn or chat_completion
        self._model = model
        self.last_observability: dict[str, Any] = {}
        self.last_speaker = "gm"
        self.last_voice_direction = None
        self._messages: list[dict] = []

    def complete_turn(self, context: dict) -> LLMTurn:
        self._messages = self._build_messages(context)
        return self._call(phase="complete_turn", accumulate=False)

    def continue_with_tools(self, context: dict, tool_results: list[dict]) -> LLMTurn:
        if not self._messages:
            self._messages = self._build_messages(context)
        for tr in tool_results or []:
            self._messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tr.get("id") or "",
                    "name": tr.get("name") or "",
                    "content": json.dumps(tr.get("result") or tr, ensure_ascii=False)[:6000],
                }
            )
        return self._call(phase="continue_with_tools", accumulate=True)

    def narrate_after_tools(self, context: dict, tool_results: list[dict]) -> str:
        messages = list(self._messages) if self._messages else self._build_messages(context)
        messages.append(
            {
                "role": "user",
                "content": (
                    "Tool results (authoritative — do not invent dice):\n"
                    f"{json.dumps(tool_results, ensure_ascii=False)[:4000]}\n"
                    "Write short public narration for the table. "
                    "If a Roll Call is pending, speak the call as the GM: name the Character, "
                    "the skill, the dice, and the DC. "
                    "Do not write stage directions, asterisks, or 'waiting for the player'."
                ),
            }
        )
        resp = self._chat(
            messages=messages,
            tools=None,
            model=self._model or default_model(),
            purpose="gm_narration",
            temperature=0.5,
            max_tokens=512,
        )
        self._record_obs(resp, phase="narrate_after_tools", accumulate=True)
        content = ((resp.get("message") or {}).get("content") or "").strip() or "The moment passes."
        text, speaker, voice_direction = parse_spoken_content(content)
        self.last_speaker = speaker
        self.last_voice_direction = voice_direction
        return text or "The moment passes."

    def _call(self, *, phase: str, accumulate: bool) -> LLMTurn:
        tools = openai_tool_definitions()
        resp = self._chat(
            messages=self._messages,
            tools=tools,
            model=self._model or default_model(),
            purpose="gm_turn",
            temperature=0.4,
            max_tokens=1024,
        )
        self._record_obs(resp, phase=phase, accumulate=accumulate)
        content = ((resp.get("message") or {}).get("content") or "").strip()
        tool_calls = validate_tool_calls(resp.get("tool_calls") or [])
        self._messages.append(_assistant_message_with_tools(resp, tool_calls))
        text, speaker, voice_direction = parse_spoken_content(content)
        self.last_speaker = speaker
        self.last_voice_direction = voice_direction
        return LLMTurn(
            tool_calls=tool_calls,
            narration=text,
            speaker=speaker,
            voice_direction=voice_direction,
        )

    def _record_obs(self, resp: dict, phase: str, accumulate: bool = False) -> None:
        usage = resp.get("usage") or {}
        latency = float(resp.get("latency_ms") or 0)
        prev = self.last_observability if accumulate else {}
        tokens_in = int(usage.get("prompt_tokens") or 0) + int(prev.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0) + int(
            prev.get("completion_tokens") or 0
        )
        self.last_observability = {
            "purpose": "gm_turn",
            "phase": phase,
            "model": resp.get("model") or self._model or default_model(),
            "latency_ms": float(prev.get("latency_ms") or 0) + latency,
            "prompt_tokens": tokens_in or None,
            "completion_tokens": tokens_out or None,
            "provider": "9router",
        }

    def _build_messages(self, context: dict) -> list[dict]:
        state = context.get("campaign_state") or {}
        blueprint = context.get("blueprint") or {}
        excerpts = context.get("rules_excerpts") or []
        rules_block = "\n\n".join(
            f"- {ex.get('text', '')[:800]}" for ex in excerpts[:4] if ex.get("text")
        ) or "(no rule excerpts retrieved)"
        purpose = context.get("purpose") or "gm_turn"
        system = (
            "You are the Game Master Runtime for a multiplayer tabletop session. "
            "Use lookup_rules to consult the uploaded book when unsure whether a "
            "Player Character check is required, or which skill, DC, and dice notation to use. "
            "For a Player Character check, call request_roll — never invent totals "
            "and never use roll_dice or perform_check for that PC. "
            "When you call request_roll, the public narration MUST speak the Roll Call "
            "as table speech in the same language as the scene: address the Character, "
            "name the skill, the dice notation, and the DC. "
            "If the Player may choose between checks, pass alternatives and speak both "
            "options so they can pick. Never mash 'or'/'ou' into a single skill name "
            "without alternatives. If the declared action already commits to one approach, "
            "issue a single check. "
            "Example: 'Kael, faça um teste de Sabedoria (Percepção), 1d20+3, CD 13.' "
            "Never write stage directions such as 'waiting for the player', "
            "'aguardando a rolagem', asterisks, or parenthetical asides about waiting. "
            "Hidden GM/NPC rolls may use roll_dice immediately. "
            "Light Combat Encounter tracker: when a fight starts, call lookup_rules "
            "for initiative/attack/damage procedures from the uploaded book, then "
            "begin_combat. Set initiative with set_combatant_initiative using server "
            "dice totals. Narrate whose turn it is from campaign_state.combat. "
            "After a resolved beat call next_turn. Never invent HP — use apply_harm "
            "or apply_heal after dice. Call end_combat when the fight ends. "
            "Keep public narration concise and in-world. "
            "Do not decide a PC's voluntary actions. "
            "Never narrate your planning ('I am reading…', 'I'll prepare…') — "
            "only describe what the table sees and hears. "
            "When generating spoken narration, you may return a JSON object "
            '{"text": "...", "speaker": "gm", "voice_direction": {"tags": ["[whispers]"]}}. '
            "Voice direction affects only delivery of the generated narration. "
            "It must never modify game rules, world state, character state, inventory, "
            "combat state, or quests. Prefer concise, natural audio tags appropriate "
            "for ElevenLabs. Plain narration text is also fine."
        )
        if purpose == "session_opening":
            system += (
                " This is the SESSION OPENING. Deliver exactly two short beats: "
                "(1) a concise campaign overview from campaign_overview, "
                "(2) the starting hook from campaign_start_hook as the live scene. "
                "Stay faithful to that material — do not invent a new premise. "
                "Address the table, not a single PC. Keep total narration brief. "
                "Call update_world_state with scene and location. No dice yet unless essential."
            )
        if purpose == "roll_resolution":
            system += (
                " This is ROLL RESOLUTION. resolved_roll is authoritative. "
                "Narrate success or failure for the table. "
                "You may update_world_state. Do not call request_roll."
            )
        party = context.get("party") or []
        brief = context.get("opening_brief") or {}
        sheet = context.get("actor_sheet") or {}
        user = {
            "purpose": purpose,
            "player_action": context.get("player_action"),
            "character_name": context.get("character_name"),
            "actor_character_id": context.get("actor_character_id"),
            "system_preset": context.get("system_preset") or "generic",
            "actor_sheet": {
                "class": sheet.get("class"),
                "level": sheet.get("level"),
                "abilities": (sheet.get("abilities") or "")[:400],
                "raw_excerpt": (sheet.get("raw_excerpt") or "")[:500],
            },
            "party": [{"name": p.get("name")} for p in party[:6]],
            "campaign_state": {
                "scene": state.get("scene"),
                "location": state.get("location"),
                "notes": (state.get("notes") or [])[-5:],
                "last_dice": state.get("last_dice"),
                "pending_check": state.get("pending_check"),
                "clocks": state.get("clocks"),
                "npc_flags": state.get("npc_flags"),
                "characters": state.get("characters") or {},
                "combat": state.get("combat"),
            },
            "resolved_roll": context.get("resolved_roll"),
            "blueprint_title": brief.get("title") or blueprint.get("title"),
            "blueprint_tone": (brief.get("tone") or blueprint.get("tone") or "")[:200],
            "campaign_overview": (brief.get("overview") or blueprint.get("premise") or "")[:500],
            "campaign_start_hook": (brief.get("start_hook") or "")[:400],
            "rules_excerpts": rules_block,
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ]
