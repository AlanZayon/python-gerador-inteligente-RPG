"""Voice providers — STT / TTS interfaces separate from 9router."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Protocol


@dataclass
class VoiceAudio:
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


class SpeechToTextProvider(Protocol):
    def transcribe(self, audio: bytes, content_type: str = "audio/webm") -> str: ...


class TextToSpeechProvider(Protocol):
    def synthesize(self, text: str, voice: str | None = None) -> VoiceAudio: ...


class MockSpeechToText:
    """Deterministic STT for tests and offline demos."""

    def __init__(self, transcript: str = "I look around the room."):
        self.transcript = transcript
        self.calls: list[tuple[int, str]] = []

    def transcribe(self, audio: bytes, content_type: str = "audio/webm") -> str:
        self.calls.append((len(audio or b""), content_type))
        return self.transcript


class MockTextToSpeech:
    """Deterministic TTS — returns a tiny fake audio payload."""

    def __init__(self, prefix: bytes = b"MOCKTTS"):
        self.prefix = prefix
        self.calls: list[str] = []

    def synthesize(self, text: str, voice: str | None = None) -> VoiceAudio:
        self.calls.append(text)
        payload = self.prefix + b":" + (text or "").encode("utf-8")[:200]
        return VoiceAudio(content_type="audio/mpeg", data=payload)


class DisabledSpeechToText:
    def transcribe(self, audio: bytes, content_type: str = "audio/webm") -> str:
        raise RuntimeError("STT is disabled")


class DisabledTextToSpeech:
    def synthesize(self, text: str, voice: str | None = None) -> VoiceAudio:
        raise RuntimeError("TTS is disabled")


class OpenAICompatibleSpeechToText:
    """OpenAI-compatible /v1/audio/transcriptions (not 9router)."""

    def __init__(self, *, base_url: str, api_key: str, model: str = "whisper-1"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def transcribe(self, audio: bytes, content_type: str = "audio/webm") -> str:
        import requests

        url = f"{self.base_url}/v1/audio/transcriptions"
        files = {"file": ("action.webm", audio, content_type or "audio/webm")}
        data = {"model": self.model}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        resp = requests.post(url, headers=headers, data=data, files=files, timeout=60)
        if resp.status_code >= 400:
            raise RuntimeError(f"STT HTTP {resp.status_code}: {resp.text[:300]}")
        payload = resp.json()
        text = (payload.get("text") or "").strip()
        if not text:
            raise RuntimeError("STT returned empty transcript")
        return text


class OpenAICompatibleTextToSpeech:
    """OpenAI-compatible /v1/audio/speech (not 9router)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str = "gpt-4o-mini-tts",
        voice: str = "alloy",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.voice = voice

    def synthesize(self, text: str, voice: str | None = None) -> VoiceAudio:
        import requests

        url = f"{self.base_url}/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "voice": voice or self.voice,
            "input": (text or "")[:4000],
            "response_format": "mp3",
        }
        resp = requests.post(url, headers=headers, json=body, timeout=60)
        if resp.status_code >= 400:
            raise RuntimeError(f"TTS HTTP {resp.status_code}: {resp.text[:300]}")
        return VoiceAudio(content_type="audio/mpeg", data=resp.content)


def _voice_base_url() -> str:
    return (
        os.getenv("VOICE_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://api.openai.com"
    ).rstrip("/")


def _voice_api_key() -> str:
    return (
        os.getenv("VOICE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()


def resolve_stt() -> SpeechToTextProvider:
    provider = (os.getenv("VOICE_STT_PROVIDER") or "mock").strip().lower()
    if provider in {"off", "disabled", "none"}:
        return DisabledSpeechToText()
    if provider in {"openai", "live"}:
        key = _voice_api_key()
        if not key:
            raise RuntimeError(
                "VOICE_STT_PROVIDER is live but VOICE_API_KEY/OPENAI_API_KEY is unset"
            )
        return OpenAICompatibleSpeechToText(
            base_url=_voice_base_url(),
            api_key=key,
            model=os.getenv("VOICE_STT_MODEL") or "whisper-1",
        )
    return MockSpeechToText(os.getenv("VOICE_MOCK_TRANSCRIPT") or "I look around the room.")


def resolve_tts() -> TextToSpeechProvider:
    provider = (os.getenv("VOICE_TTS_PROVIDER") or "mock").strip().lower()
    if provider in {"off", "disabled", "none"}:
        return DisabledTextToSpeech()
    if provider in {"openai", "live"}:
        key = _voice_api_key()
        if not key:
            raise RuntimeError(
                "VOICE_TTS_PROVIDER is live but VOICE_API_KEY/OPENAI_API_KEY is unset"
            )
        return OpenAICompatibleTextToSpeech(
            base_url=_voice_base_url(),
            api_key=key,
            model=os.getenv("VOICE_TTS_MODEL") or "gpt-4o-mini-tts",
            voice=os.getenv("VOICE_TTS_VOICE") or "alloy",
        )
    return MockTextToSpeech()
