"""MVP GM tools — server-authoritative dice and state mutations."""

from __future__ import annotations

import json
import random
import uuid
from typing import Any, Callable

from models.entities import CampaignCharacter, GameEvent, GameSession, SessionPlayer
from services.play.gm.state import dump_state, load_state

DiceRng = Callable[[int], int]


def default_dice_rng(sides: int) -> int:
    return random.randint(1, sides)


TOOL_SPECS = [
    {
        "name": "lookup_rules",
        "description": (
            "Search the uploaded rulebook for mechanics relevant to this beat. "
            "Use before calling for a Player Character check."
        ),
        "parameters": {"query": "string search for checks, DCs, skills, or procedures"},
    },
    {
        "name": "request_roll",
        "description": (
            "Issue a Roll Call for a Player Character. Does not roll. "
            "The targeted Player must confirm before the server RNG resolves. "
            "Never use roll_dice or perform_check for a PC check. "
            "If the Player may choose between two checks, pass alternatives "
            "[{skill, notation, dc}] — do not mash 'or'/'ou' into skill."
        ),
        "parameters": {
            "skill": "string skill or check name",
            "notation": "string like 1d20+3 or 3d6",
            "reason": "string why this check is called",
            "character_id": "string optional, defaults to acting Character",
            "dc": "int optional target number",
            "modifier": "int optional if notation has no modifier",
            "success_rule": "meet_or_beat or roll_under, optional",
            "alternatives": "optional list of {skill, notation, dc} when the Player chooses",
        },
    },
    {
        "name": "roll_dice",
        "description": (
            "Roll dice immediately for hidden GM/NPC rolls only. "
            "Never use this for a Player Character check — use request_roll."
        ),
        "parameters": {"notation": "string like 1d20+3", "reason": "string"},
    },
    {
        "name": "perform_check",
        "description": (
            "Roll a d20 check immediately for hidden GM/NPC rolls only. "
            "For a Player Character check use request_roll."
        ),
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
        book_id: str | None = None,
        retrieve_fn=None,
        purpose: str = "gm_turn",
    ):
        self.db = db
        self.gs = gs
        self.actor_user_id = actor_user_id
        self.actor_character_id = actor_character_id
        self.dice_rng = dice_rng or default_dice_rng
        self.book_id = book_id
        self.retrieve_fn = retrieve_fn
        self.purpose = purpose or "gm_turn"
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


def _optional_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _notation_has_explicit_modifier(notation: str) -> bool:
    text = (notation or "").lower().replace(" ", "")
    if "+" in text:
        return True
    return "-" in text[1:]


def split_skill_alternatives(skill: str) -> list[str]:
    """Split 'Perception or Stealth' / 'A (X) ou B (Y)' / 'Carisma (Intimidação ou Persuasão)'."""
    text = (skill or "").strip()
    if not text:
        return []
    top = _split_top_level_or(text)
    if len(top) > 1:
        return top
    inner = _split_ability_inner_or(text)
    if inner:
        return inner
    return [text]


def _split_top_level_or(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "(":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if depth == 0:
            rest = text[i:]
            lower = rest.lower()
            if lower.startswith(" ou "):
                chunk = "".join(buf).strip()
                if chunk:
                    parts.append(chunk)
                buf = []
                i += 4
                continue
            if lower.startswith(" or "):
                chunk = "".join(buf).strip()
                if chunk:
                    parts.append(chunk)
                buf = []
                i += 4
                continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _split_ability_inner_or(text: str) -> list[str]:
    if "(" not in text or not text.endswith(")"):
        return []
    ability, _, inner = text[:-1].partition("(")
    ability = ability.strip()
    inner_parts = _split_top_level_or(inner.strip())
    if not ability or len(inner_parts) < 2:
        return []
    return [f"{ability} ({part.strip()})" for part in inner_parts]


def _parse_alternatives_arg(raw) -> list[dict]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            names = split_skill_alternatives(raw)
            return [{"skill": name} for name in names] if len(names) > 1 else []
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if isinstance(item, str):
            skill = item.strip()
            if skill:
                out.append({"skill": skill})
            continue
        if not isinstance(item, dict):
            continue
        skill = (item.get("skill") or "").strip()
        if not skill:
            continue
        entry = {"skill": skill}
        if item.get("notation"):
            entry["notation"] = str(item.get("notation")).strip()
        if item.get("dc") is not None and item.get("dc") != "":
            entry["dc"] = _optional_int(item.get("dc"))
        if item.get("modifier") is not None and item.get("modifier") != "":
            entry["modifier"] = _optional_int(item.get("modifier")) or 0
        out.append(entry)
    return out


def attach_roll_alternatives(pending: dict, args: dict | None = None) -> dict:
    args = args or {}
    parsed = _parse_alternatives_arg(args.get("alternatives"))
    if len(parsed) < 2:
        names = split_skill_alternatives(pending.get("skill") or "")
        parsed = [{"skill": name} for name in names]
    if len(parsed) < 2:
        return pending
    notation = pending.get("notation") or "1d20"
    modifier = pending.get("modifier") or 0
    dc = pending.get("dc")
    alts = []
    for item in parsed:
        alts.append(
            {
                "skill": item["skill"],
                "notation": item.get("notation") or notation,
                "modifier": item["modifier"] if "modifier" in item else modifier,
                "dc": item["dc"] if "dc" in item else dc,
            }
        )
    pending["alternatives"] = alts
    return pending


def apply_roll_choice(
    pending: dict,
    *,
    chosen_skill: str | None = None,
    chosen_index: int | None = None,
) -> dict:
    alts = pending.get("alternatives")
    if not isinstance(alts, list) or len(alts) < 2:
        return {"ok": True, "pending": pending}
    chosen = None
    if chosen_index is not None:
        try:
            idx = int(chosen_index)
        except (TypeError, ValueError):
            idx = -1
        if 0 <= idx < len(alts):
            chosen = alts[idx]
    needle = (chosen_skill or "").strip().lower()
    if chosen is None and needle:
        exact = [a for a in alts if (a.get("skill") or "").strip().lower() == needle]
        if len(exact) == 1:
            chosen = exact[0]
        else:
            partial = [a for a in alts if needle in (a.get("skill") or "").lower()]
            if len(partial) == 1:
                chosen = partial[0]
    if chosen is None:
        return {"ok": False, "error": "needs_choice", "alternatives": alts}
    pending["skill"] = chosen.get("skill") or pending.get("skill")
    if chosen.get("notation"):
        pending["notation"] = chosen["notation"]
    if "dc" in chosen:
        pending["dc"] = chosen.get("dc")
    if "modifier" in chosen:
        pending["modifier"] = chosen.get("modifier") or 0
    pending["chosen_skill"] = pending["skill"]
    return {"ok": True, "pending": pending}


def resolve_roll_call(
    ctx: ToolContext,
    pending_id: str | None = None,
    *,
    chosen_skill: str | None = None,
    chosen_index: int | None = None,
) -> dict:
    """Server-side RNG for a pending Roll Call. Clears pending_check."""
    pending = ctx.state.get("pending_check")
    if not isinstance(pending, dict) or not pending:
        return {"ok": False, "error": "no pending Roll Call"}
    if pending_id and pending.get("id") != pending_id:
        return {"ok": False, "error": "Roll Call mismatch"}
    if pending.get("character_id") != ctx.actor_character_id:
        return {"ok": False, "error": "character does not match Roll Call"}
    applied = apply_roll_choice(
        pending, chosen_skill=chosen_skill, chosen_index=chosen_index
    )
    if not applied.get("ok"):
        return applied
    pending = applied["pending"]

    notation = pending.get("notation") or "1d20"
    n, sides, notation_mod = _parse_notation(notation)
    extra_mod = _optional_int(pending.get("modifier")) or 0
    mod = notation_mod if _notation_has_explicit_modifier(notation) else extra_mod
    rolls = [ctx.dice_rng(sides) for _ in range(n)]
    total = sum(rolls) + mod
    dc = _optional_int(pending.get("dc"))
    rule = (pending.get("success_rule") or "meet_or_beat").strip()
    success = None
    if dc is not None:
        success = total <= dc if rule == "roll_under" else total >= dc
    result = {
        "notation": notation,
        "rolls": rolls,
        "modifier": mod,
        "total": total,
        "dc": dc,
        "success": success,
        "skill": pending.get("skill") or "check",
        "reason": pending.get("reason") or "",
        "success_rule": rule,
        "character_id": pending.get("character_id"),
    }
    ctx.state["last_dice"] = result
    ctx.state["pending_check"] = None
    event_type = "check_result" if pending.get("skill") else "dice_result"
    ctx.append_event(event_type, result, target_id=pending.get("character_id"))
    ctx.persist_state()
    out = {"ok": True, "result": result}
    ctx.tool_results.append({"name": "confirm_roll", "args": {"pending_id": pending_id}, "result": out})
    return out


def execute_tool(ctx: ToolContext, name: str, args: dict) -> dict:
    args = args or {}
    if name == "lookup_rules":
        from services.play.gm.rag_context import lookup_rule_excerpts

        query = (args.get("query") or "").strip()
        excerpts = lookup_rule_excerpts(
            book_id=ctx.book_id,
            query=query,
            top_k=4,
            retrieve_fn=ctx.retrieve_fn,
        )
        out = {"ok": True, "result": {"excerpts": excerpts, "query": query}}
    elif name == "request_roll":
        if ctx.purpose == "roll_resolution":
            out = {"ok": False, "error": "cannot issue a Roll Call during roll resolution"}
        elif ctx.state.get("pending_check"):
            out = {"ok": False, "error": "a Roll Call is already pending"}
        else:
            character_id = (args.get("character_id") or ctx.actor_character_id or "").strip()
            if not character_id:
                out = {"ok": False, "error": "character_id required"}
            elif not _character_claimed_in_session(ctx, character_id):
                out = {"ok": False, "error": "character is not claimed in this session"}
            else:
                rule = (args.get("success_rule") or "meet_or_beat").strip()
                if rule not in {"meet_or_beat", "roll_under"}:
                    rule = "meet_or_beat"
                pending = {
                    "id": str(uuid.uuid4()),
                    "character_id": character_id,
                    "skill": (args.get("skill") or "check").strip() or "check",
                    "notation": (args.get("notation") or "1d20").strip() or "1d20",
                    "modifier": _optional_int(args.get("modifier")) or 0,
                    "dc": _optional_int(args.get("dc")),
                    "success_rule": rule,
                    "reason": (args.get("reason") or "").strip(),
                }
                attach_roll_alternatives(pending, args)
                ctx.state["pending_check"] = pending
                ctx.append_event("roll_requested", pending, target_id=character_id)
                ctx.persist_state()
                out = {"ok": True, "result": pending}
    elif name == "roll_dice":
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
