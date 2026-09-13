"""ElevenLabs TTS provider — official sync SDK convert() only.

Future HTTP streaming (not implemented): POST /v1/text-to-speech/{voice_id}/stream
via ``text_to_speech.stream``. Do not use the TTS WebSocket stream-input for eleven_v3;
that endpoint does not support eleven_v3.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from services.voice.errors import TTSError, classify_exception
from services.voice.models import AudioResult, TTSRequest, VoiceAudio

logger = logging.getLogger(__name__)

PROVIDER_NAME = "elevenlabs"


def content_type_for_output_format(output_format: str | None) -> str:
    fmt = (output_format or "mp3_44100_128").lower()
    if fmt.startswith("mp3_"):
        return "audio/mpeg"
    if fmt.startswith("wav_"):
        return "audio/wav"
    if fmt.startswith("opus_"):
        return "audio/opus"
    if fmt.startswith("pcm_"):
        return "audio/pcm"
    if fmt.startswith("ulaw_"):
        return "audio/basic"
    if fmt.startswith("alaw_"):
        return "audio/alaw"
    return "audio/mpeg"


def _collect_audio(raw: Any) -> bytes:
    if raw is None:
        return b""
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    if isinstance(raw, str):
        return raw.encode("utf-8")
    return b"".join(chunk for chunk in raw if chunk)


class ElevenLabsTTSProvider:
    """Text-to-speech via ``ElevenLabs.text_to_speech.convert``.

    Does not accept invented fields (emotion, pace, delivery). Audio Tags belong in ``text``.
    """

    def __init__(
        self,
        *,
        api_key: str,
        default_voice_id: str,
        model_id: str = "eleven_v3",
        output_format: str = "mp3_44100_128",
        timeout_seconds: int = 30,
        max_retries: int = 2,
        client: Any | None = None,
        sleep: Any = time.sleep,
    ):
        self.api_key = api_key
        self.default_voice_id = default_voice_id
        self.model_id = model_id
        self.output_format = output_format
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, int(max_retries))
        self._sleep = sleep
        self._client = client

    def _client_or_create(self) -> Any:
        if self._client is not None:
            return self._client
        from elevenlabs import ElevenLabs

        self._client = ElevenLabs(api_key=self.api_key)
        return self._client

    def synthesize(self, text: str, voice: str | None = None) -> VoiceAudio:
        result = self.synthesize_request(
            TTSRequest(
                text=text,
                voice_id=voice or self.default_voice_id,
                model_id=self.model_id,
                output_format=self.output_format,
            )
        )
        return result.to_voice_audio()

    def synthesize_request(self, request: TTSRequest) -> AudioResult:
        voice_id = (request.voice_id or self.default_voice_id or "").strip()
        model_id = (request.model_id or self.model_id or "").strip() or "eleven_v3"
        output_format = (request.output_format or self.output_format or "").strip() or "mp3_44100_128"
        text = request.text or ""
        if not voice_id:
            raise TTSError("TTS voice_id is required", retryable=False)
        if not text.strip():
            raise TTSError("TTS text is empty", retryable=False)

        attempts = self.max_retries + 1
        started = time.perf_counter()
        logger.info(
            "tts.request.started provider=%s model=%s voice_id=%s",
            PROVIDER_NAME,
            model_id,
            voice_id,
        )
        last_error: TTSError | None = None
        for attempt in range(1, attempts + 1):
            try:
                client = self._client_or_create()
                raw = client.text_to_speech.convert(
                    voice_id=voice_id,
                    text=text,
                    model_id=model_id,
                    output_format=output_format,
                    request_options={
                        "timeout_in_seconds": self.timeout_seconds,
                        "max_retries": 0,
                    },
                )
                audio = _collect_audio(raw)
                if not audio:
                    raise TTSError("TTS returned empty audio body", retryable=False)
                latency_ms = (time.perf_counter() - started) * 1000.0
                logger.info(
                    "tts.request.completed provider=%s model=%s voice_id=%s "
                    "latency_ms=%.1f status=%s audio_size=%s",
                    PROVIDER_NAME,
                    model_id,
                    voice_id,
                    latency_ms,
                    200,
                    len(audio),
                )
                return AudioResult(
                    audio=audio,
                    content_type=content_type_for_output_format(output_format),
                    provider=PROVIDER_NAME,
                    voice_id=voice_id,
                    model_id=model_id,
                    duration_ms=None,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = classify_exception(exc)
                logger.info(
                    "tts.request.failed provider=%s model=%s voice_id=%s "
                    "status=%s retryable=%s attempt=%s err=%s",
                    PROVIDER_NAME,
                    model_id,
                    voice_id,
                    last_error.status_code,
                    last_error.retryable,
                    attempt,
                    str(last_error)[:300],
                )
                if not last_error.retryable or attempt >= attempts:
                    raise last_error from exc
                wait = last_error.retry_after_seconds
                if wait is None:
                    wait = min(8.0, 2**attempt)
                self._sleep(wait)
        raise last_error or TTSError("TTS request failed", retryable=False)
