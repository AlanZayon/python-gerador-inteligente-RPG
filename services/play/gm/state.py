"""Minimal Campaign State helpers."""

from __future__ import annotations

import json
from copy import deepcopy


EMPTY_STATE = {
    "scene": "",
    "location": "",
    "npc_flags": {},
    "clocks": {},
    "notes": [],
    "last_dice": None,
    "pending_check": None,
    "quests": {},
    "characters": {},
}


def empty_state() -> dict:
    return deepcopy(EMPTY_STATE)


def load_state(raw: str | None) -> dict:
    if not raw:
        return empty_state()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return empty_state()
    if not isinstance(data, dict):
        return empty_state()
    state = empty_state()
    state.update({k: v for k, v in data.items() if k in state})
    return state


def dump_state(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False)
