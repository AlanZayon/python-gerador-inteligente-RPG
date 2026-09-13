"""GM → VoiceDirector seam. Does not import the ElevenLabs SDK."""

from __future__ import annotations

from typing import Any

from services.voice.director import build_voice_director
from services.voice.models import Narration, VoiceDirection


def synthesize_table_audio(
    *,
    text: str,
    speaker: str = "gm",
    voice_direction: VoiceDirection | None = None,
    tts: Any | None = None,
) -> dict | None:
    director = build_voice_director(tts)
    result = director.render(
        Narration(
            text=text,
            speaker=speaker or "gm",
            voice_direction=voice_direction,
        )
    )
    return result.to_dict() if result else None


def gm_audio_envelope(
    *,
    session_id: str,
    actor_id: str | None,
    audio_dict: dict,
    extra_payload: dict | None = None,
) -> dict:
    payload = {
        "content_type": audio_dict["content_type"],
        "data_base64": audio_dict["data_base64"],
        "byte_length": audio_dict["byte_length"],
        "for_narration": True,
    }
    for key in ("provider", "voice_id", "model_id", "speaker"):
        if audio_dict.get(key):
            payload[key] = audio_dict[key]
    if extra_payload:
        payload.update(extra_payload)
    return {
        "version": 1,
        "type": "gm_audio",
        "session_id": session_id,
        "event_id": None,
        "seq": None,
        "actor_id": actor_id,
        "target_id": None,
        "payload": payload,
        "created_at": None,
    }
