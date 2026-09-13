"""ElevenLabs / voice-profile configuration from env. Never log the API key."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from services.voice.models import VoiceProfile

logger = logging.getLogger(__name__)

_FALSE = {"0", "false", "no", "off", "disabled"}


def _truthy(raw: str | None, default: bool = True) -> bool:
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() not in _FALSE


def elevenlabs_enabled() -> bool:
    return _truthy(os.getenv("ELEVENLABS_ENABLED"), default=True)


def elevenlabs_api_key() -> str:
    return (os.getenv("ELEVENLABS_API_KEY") or "").strip()


def elevenlabs_default_voice_id() -> str:
    return (os.getenv("ELEVENLABS_DEFAULT_VOICE_ID") or "").strip()


def elevenlabs_default_model_id() -> str:
    return (os.getenv("ELEVENLABS_DEFAULT_MODEL_ID") or "eleven_v3").strip() or "eleven_v3"


def elevenlabs_output_format() -> str:
    return (os.getenv("ELEVENLABS_OUTPUT_FORMAT") or "mp3_44100_128").strip() or "mp3_44100_128"


def elevenlabs_timeout_seconds() -> int:
    raw = (os.getenv("ELEVENLABS_TIMEOUT_SECONDS") or "30").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 30


def elevenlabs_max_retries() -> int:
    raw = (os.getenv("ELEVENLABS_MAX_RETRIES") or "2").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 2


def _parse_profile_map(payload: dict) -> dict[str, VoiceProfile]:
    voices = payload.get("voices") if isinstance(payload.get("voices"), dict) else payload
    profiles: dict[str, VoiceProfile] = {}
    if not isinstance(voices, dict):
        return profiles
    for speaker, spec in voices.items():
        key = str(speaker or "").strip().lower()
        if not key:
            continue
        voice_id = ""
        if isinstance(spec, str):
            voice_id = spec.strip()
        elif isinstance(spec, dict):
            voice_id = str(spec.get("voice_id") or "").strip()
        if voice_id:
            profiles[key] = VoiceProfile(speaker=key, voice_id=voice_id)
    return profiles


def load_voice_profiles() -> dict[str, VoiceProfile]:
    raw_json = (os.getenv("VOICE_PROFILES_JSON") or "").strip()
    if raw_json:
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            logger.info("tts.voice_profiles.invalid source=VOICE_PROFILES_JSON")
            payload = {}
        if isinstance(payload, dict):
            return _parse_profile_map(payload)

    path_raw = (os.getenv("VOICE_PROFILES_PATH") or "").strip()
    if not path_raw:
        return {}
    path = Path(path_raw)
    if not path.is_file():
        logger.info("tts.voice_profiles.missing path=%s", path_raw)
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.info("tts.voice_profiles.invalid source=VOICE_PROFILES_PATH")
        return {}
    if isinstance(payload, dict):
        return _parse_profile_map(payload)
    return {}
