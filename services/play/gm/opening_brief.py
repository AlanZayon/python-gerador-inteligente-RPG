"""Derive a short session-opening brief from Campaign Blueprint / manuscript."""

from __future__ import annotations

import re
from typing import Any


OVERVIEW_MAX = 500
HOOK_MAX = 400


def _clip(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for sep in (". ", "! ", "? ", "; "):
        idx = cut.rfind(sep)
        if idx > max_chars // 2:
            return cut[: idx + 1].strip()
    return cut.rstrip(" ,;:") + "…"


def _from_manuscript(manuscript: str) -> tuple[str, str]:
    from services.campaign_parse import parse_campaign

    parsed = parse_campaign(manuscript)
    overview = ""
    hook = ""
    for sec in parsed.get("sections") or []:
        body = (sec.get("content") or "").strip()
        if not body:
            continue
        if sec.get("type") == "overview" and not overview:
            overview = body
        elif sec.get("type") == "hook" and not hook:
            hook = body
    return overview, hook


def _overview_from_blueprint(blueprint: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("premise", "central_conflict", "stakes", "thematic_question"):
        val = str(blueprint.get(key) or "").strip()
        if val and val not in parts:
            parts.append(val)
    return " ".join(parts)


def _hook_from_blueprint(blueprint: dict[str, Any]) -> str:
    sessions = blueprint.get("sessions") or []
    sess: dict[str, Any] = {}
    for raw in sessions:
        if isinstance(raw, dict):
            sess = raw
            break
    scenes = sess.get("scenes") or [] if sess else []
    if scenes and isinstance(scenes[0], dict):
        sc = scenes[0]
        bits = [
            str(sc.get("name") or "").strip(),
            str(sc.get("location") or "").strip(),
            str(sc.get("purpose") or "").strip(),
        ]
        bits = [b for b in bits if b]
        if bits:
            return ". ".join(bits)

    title = str(sess.get("title") or "").strip()
    objectives = sess.get("objectives") or []
    obj = ""
    if objectives:
        obj = str(objectives[0] or "").strip()
    if title or obj:
        return ". ".join(p for p in (title, obj) if p)

    locations = blueprint.get("locations") or []
    if locations and isinstance(locations[0], dict):
        loc = locations[0]
        name = str(loc.get("name") or "").strip()
        desc = str(loc.get("description") or loc.get("purpose") or "").strip()
        return ". ".join(p for p in (name, desc) if p)

    return ""


def build_opening_brief(
    blueprint: dict[str, Any] | None,
    manuscript: str | None = None,
) -> dict[str, str]:
    """Return short overview + start_hook grounded in campaign material.

    Prefer manuscript ## Overview / ## Starting Hook when present; otherwise
    synthesize from the Campaign Blueprint (canonical for play).
    """
    blueprint = blueprint if isinstance(blueprint, dict) else {}
    title = str(blueprint.get("title") or "").strip() or "the adventure"
    tone = str(blueprint.get("tone") or "").strip()

    overview_raw = ""
    hook_raw = ""
    if manuscript and manuscript.strip():
        overview_raw, hook_raw = _from_manuscript(manuscript)

    if not overview_raw:
        overview_raw = _overview_from_blueprint(blueprint)
    if not hook_raw:
        hook_raw = _hook_from_blueprint(blueprint)

    overview = _clip(overview_raw, OVERVIEW_MAX)
    start_hook = _clip(hook_raw, HOOK_MAX)

    if not overview:
        overview = f"Trouble gathers around {title}."
    if not start_hook:
        start_hook = overview

    return {
        "title": title,
        "tone": tone,
        "overview": overview,
        "start_hook": start_hook,
    }
