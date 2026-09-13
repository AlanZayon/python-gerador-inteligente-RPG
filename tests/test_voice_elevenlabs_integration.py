"""Optional live ElevenLabs convert() test. Disabled unless explicitly enabled.

  ELEVENLABS_INTEGRATION_TEST=true ELEVENLABS_API_KEY=... ELEVENLABS_DEFAULT_VOICE_ID=... pytest tests/test_voice_elevenlabs_integration.py
"""

from __future__ import annotations

import os

import pytest

from services.voice.director import build_voice_director
from services.voice.models import Narration, VoiceDirection

_ENABLED = (os.getenv("ELEVENLABS_INTEGRATION_TEST") or "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


@pytest.mark.skipif(
    not _ENABLED or not (os.getenv("ELEVENLABS_API_KEY") or "").strip(),
    reason="ELEVENLABS_INTEGRATION_TEST and ELEVENLABS_API_KEY are required",
)
def test_live_elevenlabs_convert_gm_line():
    pytest.importorskip("elevenlabs")
    if not (os.getenv("ELEVENLABS_DEFAULT_VOICE_ID") or "").strip():
        pytest.skip("ELEVENLABS_DEFAULT_VOICE_ID is required for live convert()")
    os.environ.setdefault("VOICE_TTS_PROVIDER", "elevenlabs")
    director = build_voice_director()
    result = director.render(
        Narration(
            speaker="gm",
            text="A porta começa a se abrir lentamente.",
            voice_direction=VoiceDirection(tags=["[slowly]"]),
        )
    )
    assert result is not None
    assert result.provider == "elevenlabs"
    assert result.model_id == (os.getenv("ELEVENLABS_DEFAULT_MODEL_ID") or "eleven_v3")
    assert len(result.audio) > 100
    assert result.content_type.startswith("audio/")
