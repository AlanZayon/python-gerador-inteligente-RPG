# 10. Voice (STT / TTS)

[← Operations](06-operations.md) · [Index](README.md) · [Next: Play →](11-play-overview.md)

---

## Architecture

```text
Player mic → 9router STT → GameMasterRuntime (9router LLM + tools)
  → Campaign State saved
  → VoiceDirector → ElevenLabs TTS (or mock / 9router TTS)
  → WebSocket gm_audio → Vue plays bytes
```

The API key never leaves the backend. The browser only receives `content_type` + `data_base64`.

## Setup

```bash
# .env
VOICE_TTS_PROVIDER=elevenlabs
ELEVENLABS_ENABLED=true
ELEVENLABS_API_KEY=          # secret starting with sk_ (not the key ID)
ELEVENLABS_DEFAULT_VOICE_ID= # from ElevenLabs voice library
ELEVENLABS_DEFAULT_MODEL_ID=eleven_v3
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
ELEVENLABS_TIMEOUT_SECONDS=30
VOICE_STT_PROVIDER=9router   # STT stays on 9router
```

Copy [config/voices.example.json](../../config/voices.example.json) and point `VOICE_PROFILES_PATH` at your file, or set `VOICE_PROFILES_JSON`. Speakers (`gm`, `villain`, …) map to `voice_id`. Unknown speakers fall back to the GM voice.

## Model

Default model is configurable `eleven_v3`. Expressiveness uses **Audio Tags** in the text (for example `[whispers]`), not invented API fields named emotion/pace/delivery. Tags are applied only for the `eleven_v3*` family so 9router TTS does not speak the brackets aloud.

## Manual test

```bash
python scripts/gm_voice_test.py --text "A porta começa a se abrir lentamente..." --speaker gm
```

Requires `ELEVENLABS_API_KEY` and `ELEVENLABS_DEFAULT_VOICE_ID`. Not run in CI.

Live API pytest: `ELEVENLABS_INTEGRATION_TEST=true pytest tests/test_voice_elevenlabs_integration.py`.

## Security

Never put `ELEVENLABS_API_KEY` in the Vue app or client bundles. Frontend playback is the existing `gm_audio` WebSocket payload only.
