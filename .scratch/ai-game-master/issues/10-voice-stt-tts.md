# 10: Voice (STT in → TTS out)

**What to build:** A Player can speak an action; STT produces text that enters the same action queue with identity from the authenticated connection. GM narration is spoken via TTS and delivered to the table. Provider interfaces support mocks; text input remains fully usable if voice is disabled.

**Blocked by:** 07 — WebSocket sync + reconnect; 08 — Live 9router GM + RAG

**Status:** resolved

- [x] STT and TTS sit behind provider interfaces with mock implementations for tests
- [x] Voice actions use connection identity, not transcript content, for Player binding
- [x] Transcribed text shares the same FIFO GM path as typed actions
- [x] TTS audio (or URL/stream handle) is delivered to session members after narration
- [x] App remains playable text-only when voice providers are unset
- [x] Tests cover STT→action and narration→TTS with mocks

## Answer

Voice providers live in `services/voice` (`mock` default, `off`, OpenAI-compatible live). `submit_voice_action` STT→same FIFO as text; actor is auth `user_id`. GM flight optionally synthesizes TTS and publishes `gm_audio` hub events (base64 MVP). HTTP `POST /sessions/:id/actions/voice`; Vue Lobby hold-to-speak + playback. Text path remains primary (`speak=false` / `VOICE_TTS_PROVIDER=off`).
