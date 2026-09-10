"""Voice providers — STT / TTS via 9router (OpenAI-compatible audio APIs)."""

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


def _normalize_openai_base(url: str) -> str:
    """Return origin without trailing /v1 so callers can append /v1/... once."""
    u = (url or "").strip().rstrip("/")
    if u.endswith("/v1"):
        u = u[:-3]
    return u.rstrip("/")


def _ninerouter_base() -> str:
    return _normalize_openai_base(
        os.getenv("VOICE_BASE_URL")
        or os.getenv("NINEROUTER_URL")
        or os.getenv("LLAMA_BASE_URL")
        or "http://localhost:20128"
    )


def _ninerouter_key() -> str:
    return (
        os.getenv("VOICE_API_KEY")
        or os.getenv("NINEROUTER_KEY")
        or os.getenv("NINEROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()


def _extension_for_content_type(content_type: str) -> str:
    ct = (content_type or "").lower()
    if "wav" in ct:
        return "wav"
    if "mpeg" in ct or "mp3" in ct:
        return "mp3"
    if "ogg" in ct:
        return "ogg"
    if "mp4" in ct or "m4a" in ct:
        return "m4a"
    return "webm"


class NineRouterSpeechToText:
    """STT via 9router ``POST /v1/audio/transcriptions`` (OpenAI Whisper shape).

    Docs: https://github.com/decolua/9router/blob/master/skills/9router-stt/SKILL.md
    List models: ``GET /v1/models/stt``
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str = "gemini/gemini-2.5-flash",
        language: str | None = None,
    ):
        self.base_url = _normalize_openai_base(base_url)
        self.api_key = api_key
        self.model = model
        self.language = language

    def transcribe(self, audio: bytes, content_type: str = "audio/webm") -> str:
        import requests

        url = f"{self.base_url}/v1/audio/transcriptions"
        ext = _extension_for_content_type(content_type)
        files = {"file": (f"action.{ext}", audio, content_type or "audio/webm")}
        data: dict[str, str] = {"model": self.model, "response_format": "json"}
        if self.language:
            data["language"] = self.language
        headers = {"Authorization": f"Bearer {self.api_key}"}
        resp = requests.post(url, headers=headers, data=data, files=files, timeout=45)
        if resp.status_code >= 400:
            raise RuntimeError(f"STT HTTP {resp.status_code}: {resp.text[:300]}")
        ctype = (resp.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            payload = resp.json()
            text = (payload.get("text") or "").strip()
        else:
            text = (resp.text or "").strip()
        if not text:
            raise RuntimeError("STT returned empty transcript")
        return text


class NineRouterTextToSpeech:
    """TTS via 9router ``POST /v1/audio/speech``.

    Docs: https://github.com/decolua/9router/blob/master/skills/9router-tts/SKILL.md
    List models/voices: ``GET /v1/models/tts``
    ``model`` is the voice/model id from that list (e.g. gemini/…-tts).
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str = "gemini/gemini-2.5-flash-preview-tts",
        voice: str | None = None,
    ):
        self.base_url = _normalize_openai_base(base_url)
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
        body: dict = {
            "model": self.model,
            "input": (text or "")[:4000],
        }
        chosen_voice = voice or self.voice
        if chosen_voice:
            body["voice"] = chosen_voice
        # Prefer raw audio bytes; fall back to JSON {audio: base64} if gateway returns it.
        resp = requests.post(url, headers=headers, json=body, timeout=25)
        if resp.status_code >= 400:
            raise RuntimeError(f"TTS HTTP {resp.status_code}: {resp.text[:300]}")

        ctype = (resp.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            payload = resp.json()
            b64 = payload.get("audio") or payload.get("data") or ""
            if not b64:
                raise RuntimeError("TTS JSON response missing audio field")
            raw = base64.b64decode(b64)
            fmt = (payload.get("format") or "mp3").lower()
            return VoiceAudio(content_type=f"audio/{fmt}", data=raw)

        if not resp.content:
            raise RuntimeError("TTS returned empty audio body")
        out_type = "audio/mpeg"
        if "wav" in ctype:
            out_type = "audio/wav"
        elif "ogg" in ctype:
            out_type = "audio/ogg"
        return VoiceAudio(content_type=out_type, data=resp.content)


# Back-compat aliases used by older call sites / docs
OpenAICompatibleSpeechToText = NineRouterSpeechToText
OpenAICompatibleTextToSpeech = NineRouterTextToSpeech


def resolve_stt() -> SpeechToTextProvider:
    provider = (os.getenv("VOICE_STT_PROVIDER") or "mock").strip().lower()
    if provider in {"off", "disabled", "none"}:
        return DisabledSpeechToText()
    if provider in {"9router", "ninerouter", "openai", "live"}:
        key = _ninerouter_key()
        if not key:
            raise RuntimeError(
                "VOICE_STT_PROVIDER is live/9router but NINEROUTER_KEY/VOICE_API_KEY is unset"
            )
        return NineRouterSpeechToText(
            base_url=_ninerouter_base(),
            api_key=key,
            model=os.getenv("VOICE_STT_MODEL") or "gemini/gemini-2.5-flash",
            language=(os.getenv("VOICE_STT_LANGUAGE") or "").strip() or None,
        )
    return MockSpeechToText(os.getenv("VOICE_MOCK_TRANSCRIPT") or "I look around the room.")


def resolve_tts() -> TextToSpeechProvider:
    provider = (os.getenv("VOICE_TTS_PROVIDER") or "mock").strip().lower()
    if provider in {"off", "disabled", "none"}:
        return DisabledTextToSpeech()
    if provider in {"9router", "ninerouter", "openai", "live"}:
        key = _ninerouter_key()
        if not key:
            raise RuntimeError(
                "VOICE_TTS_PROVIDER is live/9router but NINEROUTER_KEY/VOICE_API_KEY is unset"
            )
        return NineRouterTextToSpeech(
            base_url=_ninerouter_base(),
            api_key=key,
            model=os.getenv("VOICE_TTS_MODEL") or "gemini/gemini-2.5-flash-preview-tts",
            voice=(os.getenv("VOICE_TTS_VOICE") or "").strip() or None,
        )
    return MockTextToSpeech()
