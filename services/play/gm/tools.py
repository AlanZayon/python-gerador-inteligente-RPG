"""MVP GM tools — server-authoritative dice and state mutations."""

from __future__ import annotations

import json
import random
from typing import Any, Callable

from models.entities import CampaignCharacter, GameEvent, GameSession, SessionPlayer
from services.play.gm.state import dump_state, load_state

DiceRng = Callable[[int], int]


def default_dice_rng(sides: int) -> int:
    return random.randint(1, sides)


TOOL_SPECS = [
    {
        "name": "roll_dice",
        "description": "Roll dice authoritatively. Never invent totals in narration.",
        "parameters": {"notation": "string like 1d20+3", "reason": "string"},
    },
    {
        "name": "perform_check",
        "description": "Roll a d20 check and persist result.",
        "parameters": {"skill": "string", "dc": "int optional", "modifier": "int"},
    },
    {
        "name": "read_world_state",
        "description": "Read current Campaign State.",
        "parameters": {},
    },
    {
        "name": "update_world_state",
        "description": "Patch scene/location/npc_flags/clocks/notes.",
        "parameters": {"patch": "object"},
    },
    {
        "name": "create_event",
        "description": "Append a game event.",
        "parameters": {"type": "string", "payload": "object"},
    },
    {
        "name": "update_character",
        "description": "Update tracked character fields in Campaign State.",
        "parameters": {"character_id": "string", "fields": "object"},
    },
    {
        "name": "update_quest",
        "description": "Update quest/front progress clocks.",
        "parameters": {"quest_id": "string", "fields": "object"},
    },
    {
        "name": "write_memory",
        "description": "Persist session, campaign, or character-private knowledge.",
        "parameters": {
            "scope": "session|campaign|character_private",
            "content": "string",
            "character_id": "string optional for character_private",
        },
    },
]

TOOL_NAMES = {spec["name"] for spec in TOOL_SPECS}


def openai_tool_definitions() -> list[dict]:
    """OpenAI-compatible tools array for chat completions."""
    tools = []
    for spec in TOOL_SPECS:
        props = {}
        required = []
        for key, desc in (spec.get("parameters") or {}).items():
            props[key] = {"type": "string", "description": str(desc)}
            if "optional" not in str(desc).lower():
                required.append(key)
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": spec["name"],
                    "description": spec["description"],
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "additionalProperties": True,
                    },
                },
            }
        )
    return tools


class ToolContext:
    def __init__(
        self,
        db,
        gs: GameSession,
        actor_user_id: str,
        actor_character_id: str | None,
        dice_rng: DiceRng | None = None,
    ):
        self.db = db
        self.gs = gs
        self.actor_user_id = actor_user_id
        self.actor_character_id = actor_character_id
        self.dice_rng = dice_rng or default_dice_rng
        self.state = load_state(gs.state_json)
        self.tool_results: list[dict[str, Any]] = []
        self.events_out: list[dict[str, Any]] = []
        self._pending_publish: list[GameEvent] = []

    def _next_seq(self) -> int:
        last = (
            self.db.query(GameEvent)
            .filter(GameEvent.game_session_id == self.gs.id)
            .order_by(GameEvent.seq.desc())
            .first()
        )
        return (last.seq if last else 0) + 1

    def append_event(
        self,
        event_type: str,
        payload: dict,
        target_id: str | None = None,
    ) -> GameEvent:
        ev = GameEvent(
            game_session_id=self.gs.id,
            seq=self._next_seq(),
            type=event_type,
            actor_id=self.actor_user_id,
            target_id=target_id,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        self.db.add(ev)
        self.db.flush()
        out = {
            "id": ev.id,
            "seq": ev.seq,
            "type": ev.type,
            "payload": payload,
        }
        self.events_out.append(out)
        self._pending_publish.append(ev)
        return ev

    def persist_state(self, bump_version: bool = False) -> None:
        self.gs.state_json = dump_state(self.state)
        if bump_version:
            self.gs.state_version = int(self.gs.state_version or 0) + 1
        if self.state.get("scene"):
            self.gs.current_scene = self.state["scene"]


def _parse_notation(notation: str) -> tuple[int, int, int]:
    text = (notation or "1d20").lower().replace(" ", "")
    mod = 0
    if "+" in text:
        text, mod_s = text.split("+", 1)
        mod = int(mod_s or 0)
    elif "-" in text[1:]:
        idx = text.find("-", 1)
        mod = -int(text[idx + 1 :] or 0)
        text = text[:idx]
    if "d" not in text:
        return 1, 20, mod
    n_s, sides_s = text.split("d", 1)
    n = int(n_s or 1)
    sides = int(sides_s or 20)
    return max(1, n), max(2, sides), mod


def _character_claimed_in_session(ctx: ToolContext, character_id: str) -> bool:
    return (
        ctx.db.query(SessionPlayer)
        .filter(
            SessionPlayer.game_session_id == ctx.gs.id,
            SessionPlayer.character_id == character_id,
        )
        .first()
        is not None
    )


def execute_tool(ctx: ToolContext, name: str, args: dict) -> dict:
    args = args or {}
    if name == "roll_dice":
        n, sides, mod = _parse_notation(args.get("notation") or "1d20")
        rolls = [ctx.dice_rng(sides) for _ in range(n)]
        total = sum(rolls) + mod
        result = {
            "notation": args.get("notation") or f"{n}d{sides}",
            "rolls": rolls,
            "modifier": mod,
            "total": total,
            "reason": args.get("reason") or "",
        }
        ctx.state["last_dice"] = result
        ctx.append_event("dice_result", result)
        ctx.persist_state()
        out = {"ok": True, "result": result}
    elif name == "perform_check":
        mod = int(args.get("modifier") or 0)
        roll = ctx.dice_rng(20)
        total = roll + mod
        dc = args.get("dc")
        success = None if dc is None else total >= int(dc)
        result = {
            "skill": args.get("skill") or "check",
            "roll": roll,
            "modifier": mod,
            "total": total,
            "dc": dc,
            "success": success,
        }
        ctx.state["last_dice"] = result
        ctx.append_event("check_result", result)
        ctx.persist_state()
        out = {"ok": True, "result": result}
    elif name == "read_world_state":
        out = {"ok": True, "result": ctx.state}
    elif name == "update_world_state":
        patch = args.get("patch") or {}
        if isinstance(patch, str):
            try:
                patch = json.loads(patch)
            except json.JSONDecodeError:
                patch = {}
        if not isinstance(patch, dict):
            patch = {}
        for key in ("scene", "location"):
            if key in patch and isinstance(patch[key], str):
                ctx.state[key] = patch[key]
        if "npc_flags" in patch and isinstance(patch["npc_flags"], dict):
            ctx.state["npc_flags"].update(patch["npc_flags"])
        if "clocks" in patch and isinstance(patch["clocks"], dict):
            ctx.state["clocks"].update(patch["clocks"])
        if "notes" in patch:
            note = patch["notes"]
            if isinstance(note, list):
                ctx.state["notes"].extend(note)
            elif isinstance(note, str):
                ctx.state["notes"].append(note)
        ctx.append_event("world_updated", {"patch": patch})
        ctx.persist_state()
        out = {"ok": True, "result": ctx.state}
    elif name == "create_event":
        payload = args.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {"text": payload}
        if not isinstance(payload, dict):
            payload = {"value": payload}
        ev_type = args.get("type") or "narration"
        ctx.append_event(ev_type, payload)
        out = {"ok": True, "result": {"type": ev_type, "payload": payload}}
    elif name == "update_character":
        character_id = args.get("character_id")
        fields = args.get("fields") or {}
        if isinstance(fields, str):
            try:
                fields = json.loads(fields)
            except json.JSONDecodeError:
                fields = {}
        if not isinstance(fields, dict):
            fields = {}
        if not character_id:
            out = {"ok": False, "error": "character_id required"}
        else:
            char = (
                ctx.db.query(CampaignCharacter)
                .filter(
                    CampaignCharacter.id == character_id,
                    CampaignCharacter.campaign_id == ctx.gs.campaign_id,
                )
                .first()
            )
            if not char:
                out = {"ok": False, "error": "character not found in campaign"}
            else:
                if not _character_claimed_in_session(ctx, character_id):
                    out = {
                        "ok": False,
                        "error": "character is not claimed in this session",
                    }
                else:
                    bucket = ctx.state["characters"].setdefault(character_id, {})
                    bucket.update(fields)
                    ctx.append_event(
                        "character_updated",
                        {"character_id": character_id, "fields": fields},
                        target_id=character_id,
                    )
                    ctx.persist_state()
                    out = {"ok": True, "result": bucket}
    elif name == "update_quest":
        quest_id = args.get("quest_id") or "main"
        fields = args.get("fields") or {}
        bucket = ctx.state["quests"].setdefault(quest_id, {})
        bucket.update(fields)
        ctx.append_event("quest_updated", {"quest_id": quest_id, "fields": fields})
        ctx.persist_state()
        out = {"ok": True, "result": bucket}
    elif name == "write_memory":
        from services.play.memory import MemoryError, write_memory

        scope = args.get("scope") or "session"
        content = args.get("content") or ""
        char_id = args.get("character_id") or (
            ctx.actor_character_id if scope == "character_private" else None
        )
        if scope == "character_private" and char_id:
            if not _character_claimed_in_session(ctx, char_id):
                out = {
                    "ok": False,
                    "error": "character is not claimed in this session",
                }
                ctx.tool_results.append({"name": name, "args": args, "result": out})
                return out
        try:
            mem = write_memory(
                campaign_id=ctx.gs.campaign_id,
                game_session_id=ctx.gs.id,
                scope=scope,
                content=content,
                character_id=char_id,
                db=ctx.db,
            )
            ctx.append_event(
                "memory_written",
                {
                    "scope": mem["scope"],
                    "character_id": mem.get("character_id"),
                    "memory_id": mem["id"],
                },
                target_id=mem.get("character_id"),
            )
            out = {"ok": True, "result": mem}
        except MemoryError as exc:
            out = {"ok": False, "error": exc.message}
    else:
        out = {"ok": False, "error": f"unknown tool {name}"}

    ctx.tool_results.append({"name": name, "args": args, "result": out})
    return out
