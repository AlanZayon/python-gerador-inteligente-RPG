"""Light Combat Encounter helpers — tracker only, not a rules engine."""

from __future__ import annotations

import json
import uuid
from typing import Any


def empty_combatant(
    *,
    name: str,
    kind: str = "npc",
    character_id: str | None = None,
    side: str = "opposition",
    hp: int | None = None,
    max_hp: int | None = None,
    resources: dict | None = None,
    status: list | None = None,
    notes: str = "",
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "kind": kind if kind in {"pc", "npc"} else "npc",
        "character_id": character_id,
        "name": (name or "Unknown").strip() or "Unknown",
        "side": side if side in {"party", "opposition", "neutral"} else "opposition",
        "initiative": None,
        "hp": hp,
        "max_hp": max_hp if max_hp is not None else hp,
        "resources": dict(resources or {}),
        "status": list(status or []),
        "notes": notes or "",
    }


def ordered_combatants(combat: dict) -> list[dict]:
    """Initiative descending; unset last; stable by original index."""
    combatants = list(combat.get("combatants") or [])
    indexed = list(enumerate(combatants))

    def sort_key(item: tuple[int, dict]):
        idx, c = item
        init = c.get("initiative")
        has = init is not None and init != ""
        try:
            val = float(init) if has else float("-inf")
        except (TypeError, ValueError):
            val = float("-inf")
            has = False
        # Higher initiative first; those without initiative last; stable by idx
        return (0 if has else 1, -val if has else 0, idx)

    indexed.sort(key=sort_key)
    return [c for _, c in indexed]


def current_combatant(combat: dict | None) -> dict | None:
    if not isinstance(combat, dict) or combat.get("status") != "active":
        return None
    ordered = ordered_combatants(combat)
    if not ordered:
        return None
    idx = int(combat.get("turn_index") or 0) % len(ordered)
    return ordered[idx]


def find_combatant(combat: dict, combatant_id: str | None = None, **_) -> dict | None:
    needle = (combatant_id or "").strip()
    if not needle:
        return None
    for c in combat.get("combatants") or []:
        if c.get("id") == needle:
            return c
        if c.get("character_id") == needle:
            return c
        if (c.get("name") or "").strip().lower() == needle.lower():
            return c
    return None


def combat_is_active(state: dict | None) -> bool:
    combat = (state or {}).get("combat")
    return isinstance(combat, dict) and combat.get("status") == "active"


def initiatives_ready(combat: dict | None) -> bool:
    if not isinstance(combat, dict):
        return False
    combatants = combat.get("combatants") or []
    if not combatants:
        return False
    for c in combatants:
        init = c.get("initiative")
        if init is None or init == "":
            return False
    return True


def character_is_current_turn(state: dict | None, character_id: str | None) -> bool:
    if not character_id:
        return True
    combat = (state or {}).get("combat")
    if not combat_is_active(state):
        return True
    # Until every combatant has initiative, any PC in the fight may act
    # (book-driven initiative rolls for the table).
    if not initiatives_ready(combat):
        return True
    current = current_combatant(combat)
    if not current:
        return True
    if current.get("kind") == "npc":
        return False
    return current.get("character_id") == character_id


def character_in_combat(state: dict | None, character_id: str | None) -> bool:
    if not character_id or not combat_is_active(state):
        return False
    combat = state.get("combat") or {}
    for c in combat.get("combatants") or []:
        if c.get("character_id") == character_id:
            return True
    return False


def append_combat_log(combat: dict, summary: str, actor: str = "") -> None:
    log = combat.setdefault("log", [])
    log.append(
        {
            "round": combat.get("round") or 1,
            "actor": actor or "",
            "summary": (summary or "")[:240],
        }
    )
    if len(log) > 40:
        del log[:-40]


def parse_jsonish(raw: Any, default=None):
    if raw is None or raw == "":
        return default
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default
    return default


def combat_public_view(combat: dict | None) -> dict | None:
    if not isinstance(combat, dict):
        return None
    ordered = ordered_combatants(combat)
    turn_index = int(combat.get("turn_index") or 0)
    current = ordered[turn_index % len(ordered)] if ordered else None
    return {
        "id": combat.get("id"),
        "status": combat.get("status"),
        "round": combat.get("round") or 1,
        "turn_index": turn_index,
        "current_combatant_id": current.get("id") if current else None,
        "current_name": current.get("name") if current else None,
        "combatants": ordered,
        "log": (combat.get("log") or [])[-8:],
    }
