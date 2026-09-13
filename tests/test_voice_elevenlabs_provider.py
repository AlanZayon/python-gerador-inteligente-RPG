"""ElevenLabsTTSProvider — mocked SDK, no live API."""

from __future__ import annotations

import pytest
from elevenlabs.core.api_error import ApiError

from services.voice.elevenlabs_tts import ElevenLabsTTSProvider
from services.voice.errors import TTSError
from services.voice.models import TTSRequest


class FakeConvert:
    def __init__(self, results):
        self.results = list(results)
        self.calls: list[dict] = []

    def convert(self, voice_id, **kwargs):
        self.calls.append({"voice_id": voice_id, **kwargs})
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, convert: FakeConvert):
        self.text_to_speech = convert


def _provider(results, max_retries=2) -> tuple[ElevenLabsTTSProvider, FakeConvert]:
    convert = FakeConvert(results)
    sleeps: list[float] = []
    provider = ElevenLabsTTSProvider(
        api_key="sk-test-not-logged",
        default_voice_id="voice-gm",
        model_id="eleven_v3",
        output_format="mp3_44100_128",
        timeout_seconds=30,
        max_retries=max_retries,
        client=FakeClient(convert),
        sleep=sleeps.append,
    )
    provider._sleeps = sleeps  # type: ignore[attr-defined]
    return provider, convert


def test_successful_synthesis_collects_iterator_bytes():
    provider, convert = _provider([[b"ID3", b"MORE"]])
    result = provider.synthesize_request(
        TTSRequest(text="A porta começa a se abrir lentamente.", voice_id="voice-gm")
    )
    assert result.audio == b"ID3MORE"
    assert result.content_type == "audio/mpeg"
    assert result.provider == "elevenlabs"
    assert result.voice_id == "voice-gm"
    assert result.model_id == "eleven_v3"
    assert result.duration_ms is None
    assert convert.calls[0]["model_id"] == "eleven_v3"
    assert convert.calls[0]["output_format"] == "mp3_44100_128"
    assert convert.calls[0]["request_options"]["max_retries"] == 0
    assert convert.calls[0]["request_options"]["timeout_in_seconds"] == 30
    assert "emotion" not in convert.calls[0]
    assert "voice_settings" not in convert.calls[0]


def test_synthesize_protocol_returns_voice_audio():
    provider, _ = _provider([b"abc"])
    audio = provider.synthesize("Hello", voice="voice-alt")
    assert audio.content_type == "audio/mpeg"
    assert audio.data == b"abc"
    assert audio.to_dict()["byte_length"] == 3


@pytest.mark.parametrize("status", [401, 403, 422])
def test_auth_and_invalid_request_are_not_retried(status):
    err = ApiError(status_code=status, body={"detail": {"message": "nope"}})
    provider, convert = _provider([err, b"should-not-run"])
    with pytest.raises(TTSError) as exc:
        provider.synthesize_request(TTSRequest(text="Hello"))
    assert exc.value.status_code == status
    assert exc.value.retryable is False
    assert len(convert.calls) == 1


def test_429_is_retried_then_succeeds():
    err = ApiError(status_code=429, headers={"retry-after": "0"}, body={})
    provider, convert = _provider([err, [b"ok"]])
    result = provider.synthesize_request(TTSRequest(text="Hello"))
    assert result.audio == b"ok"
    assert len(convert.calls) == 2
    assert provider._sleeps == [0.0]  # type: ignore[attr-defined]


def test_500_is_retried_then_succeeds():
    err = ApiError(status_code=500, body={})
    provider, convert = _provider([err, b"ok"])
    result = provider.synthesize_request(TTSRequest(text="Hello"))
    assert result.audio == b"ok"
    assert len(convert.calls) == 2


def test_timeout_is_retried():
    provider, convert = _provider([TimeoutError("timed out"), b"ok"])
    result = provider.synthesize_request(TTSRequest(text="Hello"))
    assert result.audio == b"ok"
    assert len(convert.calls) == 2


def test_exhausted_retries_raise():
    err = ApiError(status_code=429, body={})
    provider, convert = _provider([err, err, err], max_retries=2)
    with pytest.raises(TTSError) as exc:
        provider.synthesize_request(TTSRequest(text="Hello"))
    assert exc.value.retryable is True
    assert len(convert.calls) == 3


def test_400_api_key_id_message_is_surfaced():
    err = ApiError(
        status_code=400,
        body={
            "detail": {
                "status": "api_key_id_used_as_api_key",
                "code": "invalid_api_key",
                "message": "API keys start with 'sk_'.",
            }
        },
    )
    provider, convert = _provider([err, b"should-not-run"])
    with pytest.raises(TTSError) as exc:
        provider.synthesize_request(TTSRequest(text="Hello"))
    assert exc.value.status_code == 400
    assert exc.value.retryable is False
    assert "sk_" in str(exc.value)
    assert "api_key_id_used_as_api_key" in str(exc.value)
    assert len(convert.calls) == 1


def test_missing_voice_id_is_not_retryable():
    provider, _ = _provider([])
    provider.default_voice_id = ""
    with pytest.raises(TTSError) as exc:
        provider.synthesize_request(TTSRequest(text="Hello", voice_id=None))
    assert exc.value.retryable is False
