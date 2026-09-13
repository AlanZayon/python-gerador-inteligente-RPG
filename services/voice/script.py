"""Build Eleven v3 Audio Tag scripts. Tags are textual direction, not an enum."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Official convert() for eleven_v3 documents a 5,000 character limit.
ELEVEN_V3_CHAR_LIMIT = 5000

# Keep only bracketed tags like [whispers] or [evil laugh]. Not a whitelist of emotions.
_TAG_RE = re.compile(r"^\[.+\]$")


def supports_audio_tags(model_id: str | None) -> bool:
    """True for the Eleven v3 family. Other models would speak '[whispers]' aloud."""
    if not model_id:
        return False
    return model_id.strip().lower().startswith("eleven_v3")


def normalize_audio_tags(tags: list[str] | None) -> list[str]:
    """Keep well-formed ``[token]`` tags; drop the rest. Do not invent replacements."""
    kept: list[str] = []
    for raw in tags or []:
        token = (raw or "").strip()
        if not token:
            continue
        if _TAG_RE.match(token):
            kept.append(token)
        else:
            logger.info("tts.audio_tag.dropped tag=%r", token[:80])
    return kept


def build_tagged_script(
    text: str,
    tags: list[str] | None = None,
    *,
    apply_tags: bool = True,
) -> str:
    """Prefix normalized Audio Tags, then a blank line, then the spoken text."""
    body = (text or "").strip()
    if not apply_tags:
        return body
    normalized = normalize_audio_tags(tags)
    if not normalized:
        return body
    return f"{' '.join(normalized)}\n\n{body}"


def exceeds_v3_char_limit(script: str, model_id: str | None) -> bool:
    if not supports_audio_tags(model_id):
        return False
    return len(script or "") > ELEVEN_V3_CHAR_LIMIT
