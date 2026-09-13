"""Audio-tag script builder — no ElevenLabs API calls."""

from services.voice.models import VoiceDirection
from services.voice.script import (
    ELEVEN_V3_CHAR_LIMIT,
    build_tagged_script,
    exceeds_v3_char_limit,
    normalize_audio_tags,
    supports_audio_tags,
)


def test_build_tagged_script_matches_v3_layout():
    direction = VoiceDirection(tags=["[slowly]", "[whispers]"])
    script = build_tagged_script(
        "A porta começa a se abrir lentamente...",
        direction.tags,
    )
    assert script == (
        "[slowly] [whispers]\n\nA porta começa a se abrir lentamente..."
    )


def test_normalize_drops_malformed_tags_without_inventing():
    kept = normalize_audio_tags(["[whispers]", "angry", "", "  [sighs]  ", "whispers"])
    assert kept == ["[whispers]", "[sighs]"]


def test_style_is_not_injected_into_script():
    direction = VoiceDirection(style="tense", tags=["[whispers]"])
    script = build_tagged_script("Hello.", direction.tags)
    assert "tense" not in script
    assert script.startswith("[whispers]")


def test_tags_omitted_when_apply_tags_false():
    script = build_tagged_script(
        "Hello.",
        ["[whispers]"],
        apply_tags=False,
    )
    assert script == "Hello."
    assert "[whispers]" not in script


def test_supports_audio_tags_only_for_v3_family():
    assert supports_audio_tags("eleven_v3") is True
    assert supports_audio_tags("eleven_v3_conversational") is True
    assert supports_audio_tags("eleven_multilingual_v2") is False
    assert supports_audio_tags("gemini/gemini-2.5-flash-preview-tts") is False
    assert supports_audio_tags(None) is False


def test_exceeds_v3_char_limit():
    over = "x" * (ELEVEN_V3_CHAR_LIMIT + 1)
    assert exceeds_v3_char_limit(over, "eleven_v3") is True
    assert exceeds_v3_char_limit(over, "eleven_multilingual_v2") is False
    assert exceeds_v3_char_limit("short", "eleven_v3") is False
