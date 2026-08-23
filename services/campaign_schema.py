"""Campaign state schema, complexity specs, and JSON plan parsing."""

from __future__ import annotations

import json
import re
from typing import Any

COMPLEXITY_ALIASES = {
    "simple": "simples",
    "simples": "simples",
    "medium": "mediana",
    "mediana": "mediana",
    "complex": "complexa",
    "complexa": "complexa",
    "complexo": "complexa",
}

COMPLEXITY_SPEC: dict[str, dict[str, Any]] = {
    "simples": {
        "sessions": (1, 2),
        "min_npcs": 4,
        "min_factions": 2,
        "min_locations": 3,
        "min_fronts": 1,
        "min_mysteries": 0,
        "min_choices_per_session": 2,
        "min_endings": 2,
        "min_approaches": 2,
        "arcs": 1,
        "subplots": 0,
        "word_target": 1200,
        "description": "Short complete arc with real choices and more than one ending.",
    },
    "mediana": {
        "sessions": (3, 4),
        "min_npcs": 6,
        "min_factions": 3,
        "min_locations": 5,
        "min_fronts": 2,
        "min_mysteries": 1,
        "min_choices_per_session": 3,
        "min_endings": 3,
        "min_approaches": 3,
        "arcs": 2,
        "subplots": 2,
        "word_target": 2800,
        "description": "Main arc plus subplot; later sessions change based on earlier choices.",
    },
    "complexa": {
        "sessions": (5, 7),
        "min_npcs": 9,
        "min_factions": 4,
        "min_locations": 7,
        "min_fronts": 3,
        "min_mysteries": 2,
        "min_choices_per_session": 3,
        "min_endings": 4,
        "min_approaches": 3,
        "arcs": 3,
        "subplots": 3,
        "word_target": 5200,
        "description": "Interlocking arcs, rival pressures, persistent consequences, multiple mysteries.",
    },
}

PLAN_JSON_INSTRUCTIONS = """
Return ONLY valid JSON (no markdown fences) with this shape:
{
  "title": "string",
  "premise": "string, 2-4 sentences",
  "thematic_question": "string",
  "tone": "string",
  "central_conflict": "string",
  "stakes": "string",
  "themes": ["string"],
  "grounded_terms": ["string"],
  "rules_to_use": ["string"],
  "factions": [{"name": "", "want": "", "method": "", "pressure": "", "why_pcs_care": ""}],
  "npcs": [{"name": "", "role": "", "want": "", "secret": "", "tie": "", "quirk": "", "attitude": ""}],
  "locations": [{"name": "", "function": "", "senses": "", "links": []}],
  "fronts": [{"name": "", "impulse": "", "portents": [], "doom": ""}],
  "mysteries": [{"question": "", "truth": "", "clues": [{"clue": "", "source": ""}]}],
  "sessions": [{
      "number": 1,
      "title": "",
      "dramatic_function": "hook|escalation|revelation|crisis|resolution",
      "objectives": [],
      "scenes": [{"name": "", "purpose": "", "location": "", "npcs": [], "approaches": [], "failure": ""}],
      "choices": [{"decision": "", "if_a": "", "if_b": ""}],
      "clues_planted": [],
      "clock_advance": "",
      "rewards": []
  }],
  "endings": [{"condition": "", "outcome": ""}],
  "secrets_gm": []
}
""".strip()


def canonical_complexity(complexity: str) -> str:
    key = (complexity or "mediana").lower().strip()
    return COMPLEXITY_ALIASES.get(key, "mediana")


def spec_for(complexity: str) -> dict[str, Any]:
    return COMPLEXITY_SPEC[canonical_complexity(complexity)]


def parse_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    candidates = [raw]
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        candidates.append(raw[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed:
            return parsed
    return None


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _split_name_role(name: str, role: str = "") -> tuple[str, str]:
    text = (name or "").strip()
    match = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", text)
    if match:
        return match.group(1).strip(), role or match.group(2).strip()
    return text, role


def _normalize_choice(choice: Any) -> dict[str, str] | None:
    if isinstance(choice, str) and choice.strip():
        return {"decision": choice.strip(), "if_a": "", "if_b": ""}
    if not isinstance(choice, dict):
        return None
    decision = _as_str(
        choice.get("decision")
        or choice.get("choice")
        or choice.get("prompt")
        or choice.get("question")
    )
    if not decision:
        return None
    return {
        "decision": decision,
        "if_a": _as_str(choice.get("if_a") or choice.get("option_a") or choice.get("a")),
        "if_b": _as_str(choice.get("if_b") or choice.get("option_b") or choice.get("b")),
    }


def _ensure_session_choices(session: dict[str, Any], minimum: int) -> None:
    choices = list(session.get("choices") or [])
    if len(choices) >= minimum:
        return
    for scene in session.get("scenes") or []:
        failure = _as_str(scene.get("failure")) or "The opposition gains ground"
        for approach in scene.get("approaches") or []:
            if len(choices) >= minimum:
                break
            label = _as_str(approach)
            if not label:
                continue
            choices.append({
                "decision": f"Take the {label} approach in {scene.get('name') or 'this scene'}?",
                "if_a": "The scene advances on their terms",
                "if_b": failure,
            })
        if len(choices) >= minimum:
            break
    while len(choices) < minimum:
        n = len(choices) + 1
        choices.append({
            "decision": f"Session fork {n}: press the conflict or withdraw?",
            "if_a": "They gain a lasting ally or clue",
            "if_b": "A front advances and a cost is locked in",
        })
    session["choices"] = choices


def normalize_plan(plan: dict[str, Any] | None, complexity: str) -> dict[str, Any] | None:
    if not isinstance(plan, dict):
        return None
    spec = spec_for(complexity)
    title = _as_str(plan.get("title"))
    premise = _as_str(plan.get("premise") or plan.get("overview"))
    if len(title) < 3 or len(premise) < 40:
        return None

    sessions: list[dict[str, Any]] = []
    for i, raw in enumerate(_as_list(plan.get("sessions")), start=1):
        if not isinstance(raw, dict):
            continue
        try:
            number = int(raw.get("number") or i)
        except (TypeError, ValueError):
            number = i
        scenes = []
        for scene in _as_list(raw.get("scenes")):
            if not isinstance(scene, dict):
                continue
            scenes.append({
                "name": _as_str(scene.get("name")) or f"Scene {len(scenes) + 1}",
                "purpose": _as_str(scene.get("purpose")),
                "location": _as_str(scene.get("location")),
                "npcs": [_as_str(n) for n in _as_list(scene.get("npcs")) if _as_str(n)],
                "approaches": [_as_str(a) for a in _as_list(scene.get("approaches")) if _as_str(a)],
                "failure": _as_str(scene.get("failure")),
            })
            while len(scenes[-1]["approaches"]) < 2:
                defaults = ("negotiate", "investigate quietly", "force a confrontation")
                scenes[-1]["approaches"].append(defaults[len(scenes[-1]["approaches"]) % 3])
        choices = []
        for choice in _as_list(raw.get("choices")):
            normalized = _normalize_choice(choice)
            if normalized:
                choices.append(normalized)
        sessions.append({
            "number": number,
            "title": _as_str(raw.get("title")) or f"Session {number}",
            "dramatic_function": _as_str(raw.get("dramatic_function")) or "escalation",
            "objectives": [_as_str(o) for o in _as_list(raw.get("objectives")) if _as_str(o)],
            "scenes": scenes,
            "choices": choices,
            "clues_planted": [_as_str(c) for c in _as_list(raw.get("clues_planted")) if _as_str(c)],
            "clock_advance": _as_str(raw.get("clock_advance")),
            "rewards": [_as_str(r) for r in _as_list(raw.get("rewards")) if _as_str(r)],
        })

    lo, _hi = spec["sessions"]
    if len(sessions) < lo:
        return None

    for session in sessions:
        _ensure_session_choices(session, spec["min_choices_per_session"])

    npcs = []
    for raw in _as_list(plan.get("npcs")):
        if isinstance(raw, str) and raw.strip():
            raw = {"name": raw.strip()}
        if not isinstance(raw, dict):
            continue
        name, extra = _split_name_role(_as_str(raw.get("name")))
        if not name:
            continue
        npcs.append({
            "name": name,
            "role": _as_str(raw.get("role")) or extra,
            "want": _as_str(raw.get("want") or raw.get("goal")),
            "secret": _as_str(raw.get("secret")),
            "tie": _as_str(raw.get("tie") or raw.get("relationship")),
            "quirk": _as_str(raw.get("quirk")),
            "attitude": _as_str(raw.get("attitude")) or "neutral",
        })

    factions = []
    for raw in _as_list(plan.get("factions")):
        if isinstance(raw, str) and raw.strip():
            raw = {"name": raw.strip()}
        if not isinstance(raw, dict):
            continue
        name, _extra = _split_name_role(_as_str(raw.get("name")))
        if not name:
            continue
        factions.append({
            "name": name,
            "want": _as_str(raw.get("want")),
            "method": _as_str(raw.get("method")),
            "pressure": _as_str(raw.get("pressure")),
            "why_pcs_care": _as_str(raw.get("why_pcs_care")),
        })

    locations = []
    for raw in _as_list(plan.get("locations")):
        if isinstance(raw, str) and raw.strip():
            raw = {"name": raw.strip()}
        if not isinstance(raw, dict):
            continue
        name, _extra = _split_name_role(_as_str(raw.get("name")))
        if not name:
            continue
        locations.append({
            "name": name,
            "function": _as_str(raw.get("function")),
            "senses": _as_str(raw.get("senses")),
            "links": [_as_str(x) for x in _as_list(raw.get("links")) if _as_str(x)],
        })

    fronts = []
    for raw in _as_list(plan.get("fronts") or plan.get("threats")):
        if isinstance(raw, str) and raw.strip():
            raw = {"name": raw.strip()}
        if not isinstance(raw, dict):
            continue
        name, _extra = _split_name_role(_as_str(raw.get("name")))
        if not name:
            continue
        fronts.append({
            "name": name,
            "impulse": _as_str(raw.get("impulse")),
            "portents": [_as_str(p) for p in _as_list(raw.get("portents")) if _as_str(p)],
            "doom": _as_str(raw.get("doom")),
        })

    mysteries = []
    for raw in _as_list(plan.get("mysteries")):
        if not isinstance(raw, dict):
            continue
        question = _as_str(raw.get("question"))
        if not question:
            continue
        clues = []
        for clue in _as_list(raw.get("clues")):
            if isinstance(clue, dict):
                clues.append({
                    "clue": _as_str(clue.get("clue") or clue.get("text")),
                    "source": _as_str(clue.get("source")),
                })
            elif _as_str(clue):
                clues.append({"clue": _as_str(clue), "source": ""})
        mysteries.append({
            "question": question,
            "truth": _as_str(raw.get("truth")),
            "clues": [c for c in clues if c["clue"]],
        })

    endings = []
    for raw in _as_list(plan.get("endings")):
        if isinstance(raw, dict) and (_as_str(raw.get("condition")) or _as_str(raw.get("outcome"))):
            endings.append({
                "condition": _as_str(raw.get("condition")),
                "outcome": _as_str(raw.get("outcome")),
            })
        elif _as_str(raw):
            endings.append({"condition": "", "outcome": _as_str(raw)})

    return {
        "title": title,
        "premise": premise,
        "thematic_question": _as_str(plan.get("thematic_question")),
        "tone": _as_str(plan.get("tone")),
        "central_conflict": _as_str(plan.get("central_conflict") or plan.get("conflict")),
        "stakes": _as_str(plan.get("stakes")),
        "themes": [_as_str(t) for t in _as_list(plan.get("themes")) if _as_str(t)],
        "grounded_terms": [_as_str(t) for t in _as_list(plan.get("grounded_terms")) if _as_str(t)],
        "rules_to_use": [_as_str(t) for t in _as_list(plan.get("rules_to_use")) if _as_str(t)],
        "factions": factions,
        "npcs": npcs,
        "locations": locations,
        "fronts": fronts,
        "mysteries": mysteries,
        "sessions": sessions,
        "endings": endings,
        "secrets_gm": [_as_str(s) for s in _as_list(plan.get("secrets_gm")) if _as_str(s)],
        "complexity": canonical_complexity(complexity),
    }


def plan_is_structurally_complete(state: dict[str, Any], complexity: str) -> tuple[bool, list[str]]:
    spec = spec_for(complexity)
    issues: list[str] = []
    lo, _hi = spec["sessions"]
    if len(state.get("sessions") or []) < lo:
        issues.append("sessions below minimum")
    if len(state.get("npcs") or []) < spec["min_npcs"]:
        issues.append("npcs below minimum")
    if len(state.get("factions") or []) < spec["min_factions"]:
        issues.append("factions below minimum")
    if len(state.get("locations") or []) < spec["min_locations"]:
        issues.append("locations below minimum")
    if len(state.get("fronts") or []) < spec["min_fronts"]:
        issues.append("fronts below minimum")
    if spec["min_mysteries"] and len(state.get("mysteries") or []) < spec["min_mysteries"]:
        issues.append("mysteries below minimum")
    if len(state.get("endings") or []) < spec["min_endings"]:
        issues.append("endings below minimum")
    for session in state.get("sessions") or []:
        if len(session.get("choices") or []) < spec["min_choices_per_session"]:
            issues.append("session choices below minimum")
            break
        if any(len(sc.get("approaches") or []) < 2 for sc in session.get("scenes") or []):
            issues.append("scene approaches below minimum")
            break
    return not issues, issues


def name_registry(state: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "npcs": [n["name"] for n in state.get("npcs") or [] if n.get("name")],
        "factions": [f["name"] for f in state.get("factions") or [] if f.get("name")],
        "locations": [loc["name"] for loc in state.get("locations") or [] if loc.get("name")],
        "fronts": [f["name"] for f in state.get("fronts") or [] if f.get("name")],
        "terms": list(state.get("grounded_terms") or []),
    }


def state_digest(state: dict[str, Any], *, max_chars: int = 4500) -> str:
    lines = [
        f"TITLE: {state.get('title')}",
        f"PREMISE: {state.get('premise')}",
        f"THEMATIC QUESTION: {state.get('thematic_question')}",
        f"CONFLICT: {state.get('central_conflict')}",
        f"STAKES: {state.get('stakes')}",
        f"TONE: {state.get('tone')}",
        f"THEMES: {', '.join(state.get('themes') or [])}",
        f"GROUNDED TERMS: {', '.join(state.get('grounded_terms') or [])}",
        f"RULES TO USE: {', '.join(state.get('rules_to_use') or [])}",
        "FACTIONS:",
    ]
    for fac in state.get("factions") or []:
        lines.append(
            f"- {fac['name']}: wants {fac.get('want')}; method {fac.get('method')}; "
            f"if ignored: {fac.get('pressure')}"
        )
    lines.append("NPCS:")
    for npc in state.get("npcs") or []:
        lines.append(
            f"- {npc['name']} ({npc.get('role')}, {npc.get('attitude')}): wants {npc.get('want')}; "
            f"secret {npc.get('secret')}; quirk {npc.get('quirk')}"
        )
    lines.append("LOCATIONS:")
    for loc in state.get("locations") or []:
        lines.append(f"- {loc['name']}: {loc.get('function')} | {loc.get('senses')}")
    lines.append("FRONTS:")
    for front in state.get("fronts") or []:
        portents = "; ".join(front.get("portents") or [])
        lines.append(
            f"- {front['name']}: {front.get('impulse')} | {portents} | doom: {front.get('doom')}"
        )
    lines.append("MYSTERIES:")
    for mystery in state.get("mysteries") or []:
        clues = "; ".join(c.get("clue") or "" for c in mystery.get("clues") or [])
        lines.append(f"- {mystery['question']} TRUTH: {mystery.get('truth')} CLUES: {clues}")
    lines.append("SESSIONS:")
    for session in state.get("sessions") or []:
        lines.append(
            f"- S{session.get('number')} {session.get('title')} [{session.get('dramatic_function')}]"
        )
    lines.append("ENDINGS:")
    for ending in state.get("endings") or []:
        lines.append(f"- If {ending.get('condition')}: {ending.get('outcome')}")
    secrets = state.get("secrets_gm") or []
    if secrets:
        lines.append("GM SECRETS: " + " | ".join(secrets))
    return "\n".join(lines)[:max_chars]


def session_brief(session: dict[str, Any]) -> str:
    return json.dumps(session, ensure_ascii=False, indent=2)





