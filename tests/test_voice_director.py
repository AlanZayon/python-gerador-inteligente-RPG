"""VoiceProfileResolver + VoiceDirector — mocked providers, no live API."""

from __future__ import annotations

from services.voice import MockTextToSpeech, resolve_tts
from services.voice.director import VoiceDirector, VoiceProfileResolver
from services.voice.elevenlabs_tts import ElevenLabsTTSProvider
from services.voice.models import Narration, VoiceDirection, VoiceProfile


class RecordingTTS(MockTextToSpeech):
    def __init__(self):
        super().__init__(prefix=b"REC")
        self.voices: list[str | None] = []

    def synthesize(self, text: str, voice: str | None = None):
        self.voices.append(voice)
        return super().synthesize(text, voice)


def test_resolver_known_speakers():
    resolver = VoiceProfileResolver(
        {
            "gm": VoiceProfile(speaker="gm", voice_id="voice-gm"),
            "villain": VoiceProfile(speaker="villain", voice_id="voice-villain"),
        },
        default_voice_id="voice-fallback",
    )
    assert resolver.resolve("gm").voice_id == "voice-gm"
    assert resolver.resolve("villain").voice_id == "voice-villain"


def test_resolver_unknown_falls_back_to_gm():
    resolver = VoiceProfileResolver(
        {"gm": VoiceProfile(speaker="gm", voice_id="voice-gm")},
        default_voice_id="voice-fallback",
    )
    profile = resolver.resolve("unknown_npc")
    assert profile.speaker == "unknown_npc"
    assert profile.voice_id == "voice-gm"


def test_resolver_unknown_without_gm_uses_default():
    resolver = VoiceProfileResolver({}, default_voice_id="voice-fallback")
    assert resolver.resolve("goblin").voice_id == "voice-fallback"


def test_director_applies_v3_audio_tags_and_resolves_voice():
    tts = RecordingTTS()
    resolver = VoiceProfileResolver(
        {"gm": VoiceProfile(speaker="gm", voice_id="voice-gm")},
        default_voice_id="voice-gm",
    )
    director = VoiceDirector(tts, resolver, model_id="eleven_v3")
    audio = director.render(
        Narration(
            speaker="gm",
            text="A porta começa a se abrir lentamente...",
            voice_direction=VoiceDirection(style="tense", tags=["[slowly]", "[whispers]"]),
        )
    )
    assert audio is not None
    assert tts.calls == ["[slowly] [whispers]\n\nA porta começa a se abrir lentamente..."]
    assert tts.voices == ["voice-gm"]
    assert "tense" not in tts.calls[0]


def test_director_skips_tags_for_non_v3_models():
    tts = RecordingTTS()
    resolver = VoiceProfileResolver(
        {"gm": VoiceProfile(speaker="gm", voice_id="voice-gm")},
        default_voice_id="voice-gm",
    )
    director = VoiceDirector(tts, resolver, model_id="gemini/gemini-2.5-flash-preview-tts")
    director.render(
        Narration(
            speaker="gm",
            text="Hello there.",
            voice_direction=VoiceDirection(tags=["[whispers]"]),
        )
    )
    assert tts.calls == ["Hello there."]


def test_director_unknown_speaker_does_not_fail():
    tts = RecordingTTS()
    resolver = VoiceProfileResolver(
        {"gm": VoiceProfile(speaker="gm", voice_id="voice-gm")},
        default_voice_id="voice-gm",
    )
    director = VoiceDirector(tts, resolver, model_id="eleven_v3")
    audio = director.render(Narration(speaker="missing_npc", text="Boo."))
    assert audio is not None
    assert tts.voices == ["voice-gm"]


def test_resolve_tts_elevenlabs_when_configured(monkeypatch):
    monkeypatch.setenv("VOICE_TTS_PROVIDER", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_ENABLED", "true")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test-abcdefghijklmnop")
    monkeypatch.setenv("ELEVENLABS_DEFAULT_VOICE_ID", "voice-gm")
    monkeypatch.setenv("ELEVENLABS_DEFAULT_MODEL_ID", "eleven_v3")
    tts = resolve_tts()
    assert isinstance(tts, ElevenLabsTTSProvider)
    assert tts.model_id == "eleven_v3"
    assert tts.default_voice_id == "voice-gm"


def test_load_voice_profiles_from_json_env(monkeypatch):
    monkeypatch.setenv(
        "VOICE_PROFILES_JSON",
        '{"voices": {"gm": {"voice_id": "voice-gm"}, "villain": {"voice_id": "voice-v"}}}',
    )
    from services.voice.config import load_voice_profiles

    profiles = load_voice_profiles()
    assert profiles["gm"].voice_id == "voice-gm"
    assert profiles["villain"].voice_id == "voice-v"


def test_resolve_tts_elevenlabs_disabled_falls_back_to_mock(monkeypatch):
    monkeypatch.setenv("VOICE_TTS_PROVIDER", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_ENABLED", "false")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test-abcdefghijklmnop")
    tts = resolve_tts()
    assert isinstance(tts, MockTextToSpeech)
