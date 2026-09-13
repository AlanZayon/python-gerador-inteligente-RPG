"""Voice-layer DTOs. Separate from Game Master rules and Campaign State."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field


@dataclass
class VoiceAudio:
    """Ephemeral audio payload for HTTP/WebSocket delivery."""

    content_type: str
    data: bytes

    @property
    def data_base64(self) -> str:
        return base64.b64encode(self.data).decode("ascii")

    def to_dict(self) -> dict:
        return {
            "content_type": self.content_type,
            "data_base64": self.data_base64,
            "byte_length": len(self.data),
        }


@dataclass
class VoiceDirection:
    """Internal acting intent. Tags become Eleven v3 Audio Tags in the text.

    ``style`` is metadata only — never sent as ElevenLabs ``voice_settings.style``
    (that API field is a float exaggeration, not a named emotion).
    """

    style: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class VoiceProfile:
    speaker: str
    voice_id: str


@dataclass
class Narration:
    """Spoken performance request. Table text lives in ``text``; delivery is separate."""

    text: str
    speaker: str = "gm"
    voice_direction: VoiceDirection | None = None
    voice_id: str | None = None


@dataclass
class TTSRequest:
    """Provider-level synthesis request. Only official convert() fields."""

    text: str
    voice_id: str | None = None
    model_id: str | None = None
    output_format: str | None = None


@dataclass
class AudioResult:
    """Complete audio from a TTS provider. ``duration_ms`` is None unless the API returns it."""

    audio: bytes
    content_type: str
    provider: str
    voice_id: str | None = None
    model_id: str | None = None
    duration_ms: int | None = None

    @property
    def data(self) -> bytes:
        return self.audio

    @property
    def data_base64(self) -> str:
        return base64.b64encode(self.audio).decode("ascii")

    def to_voice_audio(self) -> VoiceAudio:
        return VoiceAudio(content_type=self.content_type, data=self.audio)

    def to_dict(self) -> dict:
        payload = self.to_voice_audio().to_dict()
        if self.provider:
            payload["provider"] = self.provider
        if self.voice_id:
            payload["voice_id"] = self.voice_id
        if self.model_id:
            payload["model_id"] = self.model_id
        if self.duration_ms is not None:
            payload["duration_ms"] = self.duration_ms
        return payload
