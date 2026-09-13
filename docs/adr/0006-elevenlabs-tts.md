# ElevenLabs for Game Master TTS

TTS for live play uses ElevenLabs `eleven_v3` via the official Python SDK (`text_to_speech.convert`). 9router remains the LLM and STT gateway. Optional 9router TTS stays available as `VOICE_TTS_PROVIDER=9router`.

The Game Master Runtime never imports the ElevenLabs SDK. Flow:

```text
GameMasterRuntime
  → persist Campaign State + gm_narration
  → VoiceDirector
  → TextToSpeechProvider (ElevenLabsTTSProvider)
  → gm_audio WebSocket broadcast
```

ElevenLabs is performance only. A TTS failure leaves table text and Campaign State intact.

## Why not the TTS WebSocket for v3

Official realtime TTS WebSocket (`/v1/text-to-speech/{voice_id}/stream-input`) does not support `eleven_v3`. Future streaming should use HTTP `POST /v1/text-to-speech/{voice_id}/stream` (`text_to_speech.stream`) after the MVP complete-audio path. Text-to-Dialogue is a separate API (`POST /v1/text-to-dialogue`) and is stubbed only.
