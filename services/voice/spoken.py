"""Parse optional structured spoken output. Never regex Audio Tags out of prose."""

from __future__ import annotations

import json

from services.voice.models import VoiceDirection


def parse_spoken_content(content: str) -> tuple[str, str, VoiceDirection | None]:
    """If the whole message is a JSON object with ``text``, use that.

    Otherwise treat the string as table narration with speaker=gm and no tags.
    """
    raw = (content or "").strip()
    if not raw:
        return "", "gm", None
    if raw.startswith("{") and raw.endswith("}"):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            text = payload.get("text")
            if isinstance(text, str) and text.strip():
                speaker = str(payload.get("speaker") or "gm").strip() or "gm"
                return text.strip(), speaker, _voice_direction_from_payload(payload.get("voice_direction"))
    return raw, "gm", None


def _voice_direction_from_payload(raw) -> VoiceDirection | None:
    if not isinstance(raw, dict):
        return None
    tags_in = raw.get("tags") or []
    tags: list[str] = []
    if isinstance(tags_in, list):
        tags = [str(t) for t in tags_in if t is not None and str(t).strip()]
    style = raw.get("style")
    style_s = str(style).strip() if style else None
    if not tags and not style_s:
        return None
    return VoiceDirection(style=style_s or None, tags=tags)
