"""VoiceDirector — performance only. Does not know RPG rules or Campaign State."""

from __future__ import annotations

import logging
from typing import Any

from services.voice.models import AudioResult, Narration, TTSRequest, VoiceAudio, VoiceProfile
from services.voice.script import build_tagged_script, exceeds_v3_char_limit, supports_audio_tags

logger = logging.getLogger(__name__)


class VoiceProfileResolver:
    """Map speaker names to configured voice IDs. Unknown speakers use the GM default."""

    def __init__(
        self,
        profiles: dict[str, VoiceProfile] | None = None,
        *,
        default_voice_id: str,
        default_speaker: str = "gm",
    ):
        self._profiles = {str(k).strip().lower(): v for k, v in (profiles or {}).items()}
        self._default_voice_id = (default_voice_id or "").strip()
        self._default_speaker = (default_speaker or "gm").strip().lower() or "gm"

    def resolve(self, speaker: str | None) -> VoiceProfile:
        key = (speaker or self._default_speaker).strip().lower() or self._default_speaker
        if key in self._profiles:
            return self._profiles[key]
        if self._default_speaker in self._profiles:
            fallback = self._profiles[self._default_speaker]
            return VoiceProfile(speaker=key, voice_id=fallback.voice_id)
        return VoiceProfile(speaker=key, voice_id=self._default_voice_id)


class VoiceDirector:
    """Resolve speaker → voice, apply Audio Tags when the model supports them, call TTS."""

    def __init__(
        self,
        provider: Any,
        resolver: VoiceProfileResolver | None = None,
        *,
        model_id: str | None = None,
        output_format: str | None = None,
    ):
        self.provider = provider
        self.resolver = resolver
        self.model_id = model_id or getattr(provider, "model_id", None)
        self.output_format = output_format or getattr(provider, "output_format", None)

    def render(self, narration: Narration) -> AudioResult | None:
        text = (narration.text or "").strip()
        if not text:
            return None
        profile = self._resolve_profile(narration)
        model_id = self.model_id
        apply_tags = supports_audio_tags(model_id)
        tags = list((narration.voice_direction.tags if narration.voice_direction else None) or [])
        script = build_tagged_script(text, tags, apply_tags=apply_tags)
        if exceeds_v3_char_limit(script, model_id):
            logger.info(
                "tts.request.skipped provider=%s model=%s reason=char_limit",
                getattr(self.provider, "provider", None) or type(self.provider).__name__,
                model_id,
            )
            return None
        request = TTSRequest(
            text=script,
            voice_id=profile.voice_id,
            model_id=model_id,
            output_format=self.output_format,
        )
        if hasattr(self.provider, "synthesize_request"):
            return self.provider.synthesize_request(request)
        audio: VoiceAudio = self.provider.synthesize(script, voice=profile.voice_id or None)
        return AudioResult(
            audio=audio.data,
            content_type=audio.content_type,
            provider=getattr(self.provider, "provider", None) or "tts",
            voice_id=profile.voice_id or None,
            model_id=model_id,
            duration_ms=None,
        )

    def _resolve_profile(self, narration: Narration) -> VoiceProfile:
        if (narration.voice_id or "").strip():
            return VoiceProfile(
                speaker=(narration.speaker or "gm").strip() or "gm",
                voice_id=narration.voice_id.strip(),
            )
        if self.resolver is None:
            return VoiceProfile(
                speaker=(narration.speaker or "gm").strip() or "gm",
                voice_id="",
            )
        return self.resolver.resolve(narration.speaker)


def build_voice_director(provider: Any | None = None) -> VoiceDirector:
    """Compose resolver + director from env. Game Master should call this, not the SDK."""
    from services.voice import resolve_tts
    from services.voice.config import elevenlabs_default_voice_id, load_voice_profiles

    tts = provider if provider is not None else resolve_tts()
    default_id = (
        getattr(tts, "default_voice_id", None)
        or getattr(tts, "voice", None)
        or elevenlabs_default_voice_id()
        or ""
    )
    resolver = VoiceProfileResolver(load_voice_profiles(), default_voice_id=str(default_id))
    return VoiceDirector(tts, resolver)
