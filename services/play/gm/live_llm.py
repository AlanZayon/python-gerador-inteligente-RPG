"""Live Game Master LLM via existing 9router chat completions + tools."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from services.llm_client import chat_completion, default_model
from services.play.gm.mock_llm import LLMTurn
from services.play.gm.tools import TOOL_NAMES, openai_tool_definitions

logger = logging.getLogger(__name__)


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

    def complete_turn(self, context: dict) -> LLMTurn:
        messages = self._build_messages(context)
        tools = openai_tool_definitions()
        resp = self._chat(
            messages=messages,
            tools=tools,
            model=self._model or default_model(),
            purpose="gm_turn",
            temperature=0.4,
            max_tokens=1024,
        )
        self._record_obs(resp, phase="complete_turn")
        content = ((resp.get("message") or {}).get("content") or "").strip()
        tool_calls = validate_tool_calls(resp.get("tool_calls") or [])
        return LLMTurn(tool_calls=tool_calls, narration=content)

    def narrate_after_tools(self, context: dict, tool_results: list[dict]) -> str:
        messages = self._build_messages(context)
        messages.append(
            {
                "role": "user",
                "content": (
                    "Tool results (authoritative — do not invent dice):\n"
                    f"{json.dumps(tool_results, ensure_ascii=False)[:4000]}\n"
                    "Write short public narration for the table."
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
        return ((resp.get("message") or {}).get("content") or "").strip() or "The moment passes."

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
        system = (
            "You are the Game Master Runtime for a multiplayer tabletop session. "
            "Use tools for dice, checks, and Campaign State changes. "
            "Never invent dice totals when a tool exists. "
            "Keep public narration concise. Do not decide a PC's voluntary actions."
        )
        user = {
            "player_action": context.get("player_action"),
            "character_name": context.get("character_name"),
            "campaign_state": {
                "scene": state.get("scene"),
                "location": state.get("location"),
                "notes": (state.get("notes") or [])[-5:],
                "last_dice": state.get("last_dice"),
                "clocks": state.get("clocks"),
                "npc_flags": state.get("npc_flags"),
            },
            "blueprint_title": blueprint.get("title"),
            "blueprint_premise": (blueprint.get("premise") or "")[:500],
            "rules_excerpts": rules_block,
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ]
