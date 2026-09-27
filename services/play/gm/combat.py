"""Light Combat Encounter helpers — tracker only, not a rules engine."""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from typing import Any

# Cue lists are matched against accent-stripped lowercase text (EN + PT).
_VIOLENCE_VERBS = (
    r"attack\w*|strike|strikes|striking|struck|stab\w*|slash\w*|shoot\w*|shot|"
    r"punch\w*|kick\w*|swing\w* at|charg\w* at|lunge\w* at|fire\w* at|"
    r"hit|hits|hitting|smash\w*|kill|kills|killing|murder\w*|fight|fights|fighting|"
    r"assault\w*|"
    r"atac\w*|golpe\w*|desfer\w*|esfaque\w*|apunhal\w*|flech(?:o|ar|ei|ou)|"
    r"(?:atir|dispar)\w*(?: \w+){0,3} (?:em|no|na|nos|nas|contra)|"
    r"soc(?:o|a|ar|ei|ou|amos)|chut(?:o|a|ar|ei|ou|amos)|"
    r"invist\w* contra|invest\w* contra|parto pra cima|partir pra cima|"
    r"lut(?:o|a|ar|amos|ei|ou)|brig(?:o|a|ar|amos|ou)|"
    r"mat(?:ar|amos|ei|ou)|ferir|firo|fere|feri|estoc(?:o|a|ar|ada)"
)
_VIOLENCE_RE = re.compile(rf"\b(?:{_VIOLENCE_VERBS})\b")
_NEGATED_RE = re.compile(
    rf"\b(?:nao|nunca|jamais|not|never|dont|don't|do not|won't|wont)\s+(?:\w+\s+)?(?:{_VIOLENCE_VERBS})\b"
)
_NON_COMBAT_TARGET_RE = re.compile(
    r"\b(?:door|gate|wall|lock|chest|barrel|crate|bell|rock|tree|table|dummy|target practice|"
    r"training|practice|sparring|spar|"
    r"porta|portao|parede|fechadura|bau|barril|caixote|sino|pedra|arvore|mesa|boneco|"
    r"alvo de treino|treino|treinar|pratica|praticar)\b"
)
_SURRENDER_RE = re.compile(
    r"\b(?:surrender\w*|yield\w*|give up|me rendo|rendo|render|entrego|entregar|desisto)\b"
)
_ATTACK_ROLL_RE = re.compile(
    r"\b(?:attack\w*|to hit|weapon|melee|ranged|damage|strike|"
    r"ataque\w*|atacar|arma|corpo a corpo|a distancia|dano|golpe\w*|acerto)\b"
)
_INITIATIVE_RE = re.compile(r"\b(?:initiative|iniciativa)\b")


def _fold(text: str | None) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).lower()


def looks_like_hostile_violence(text: str | None) -> bool:
    """Declared violence against a creature (not objects, practice, or surrender)."""
    folded = _fold(text)
    if not folded.strip() or not _VIOLENCE_RE.search(folded):
        return False
    if _NEGATED_RE.search(folded) or _SURRENDER_RE.search(folded):
        return False
    return not _NON_COMBAT_TARGET_RE.search(folded)


def looks_like_initiative_roll(skill: str | None, reason: str | None = None) -> bool:
    return bool(_INITIATIVE_RE.search(_fold(f"{skill or ''} {reason or ''}")))


def looks_like_attack_or_damage_roll(skill: str | None, reason: str | None = None) -> bool:
    if looks_like_initiative_roll(skill, reason):
        return False
    return bool(_ATTACK_ROLL_RE.search(_fold(f"{skill or ''} {reason or ''}")))


def combat_policy_for_turn(
    *,
    purpose: str,
    player_action: str,
    state: dict | None,
    resolved_roll: dict | None = None,
) -> dict | None:
    """Advisory for the GM when a beat looks like violence but no encounter exists."""
    if combat_is_active(state):
        return None
    if purpose == "gm_turn" and looks_like_hostile_violence(player_action):
        return {
            "combat_active": False,
            "hostile_violence_detected": True,
            "required_order": [
                "lookup_rules",
                "begin_combat",
                "initiative",
                "then_attacks_on_turn",
            ],
            "forbid": (
                "Do not request_roll attack/damage or narrate fight-ending capture "
                "while combat is inactive. If this is not violence against a creature "
                "(object, practice, surrender), ignore this policy."
            ),
        }
    roll = resolved_roll or {}
    if purpose == "roll_resolution" and looks_like_attack_or_damage_roll(
        roll.get("skill"), roll.get("reason")
    ):
        return {
            "combat_active": False,
            "attack_resolved_outside_combat": True,
            "forbid": (
                "Do not end the fight with capture, restraint, knockout, or death. "
                "If hostilities continue, lookup_rules then begin_combat and hand off "
                "to initiative."
            ),
        }
    return None


def combatant_for_character(state: dict | None, character_id: str | None) -> dict | None:
    if not character_id or not combat_is_active(state):
        return None
    for c in (state.get("combat") or {}).get("combatants") or []:
        if c.get("character_id") == character_id:
            return c
    return None


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
