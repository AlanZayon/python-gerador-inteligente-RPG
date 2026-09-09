# 11: Hardening & observability

**What to build:** Production-shaped safety for the play path: authorization on every sensitive action/tool, basic rate limits for actions/LLM/voice, structured logs correlating session/request/tool/model/latency, and tests that the GM does not voluntarily decide a Player Character’s actions.

**Blocked by:** 09 — Memory (session / campaign / character-private); 10 — Voice (STT in → TTS out)

**Status:** resolved

- [x] Non-members cannot act; non-hosts cannot perform host-only operations; tools check session/character ownership
- [x] Rate limits exist for player actions and expensive GM/voice calls (sensible defaults for personal use)
- [x] Structured logs include correlation ids for GM turns and tool execution without dumping secrets
- [x] Agency rule is covered by at least one Play Application test (GM must not invent unrequested PC voluntary actions)
- [x] Server restart still recovers Campaign State / events for an ACTIVE session (smoke/verification)

## Answer

Play authz tightened on `update_character` / private `write_memory` (must be claimed in-session). Per-user action/voice rate limits (`PLAY_*_RATE_*`, HTTP decorators). GM turns log `request_id` + session/tool metadata without secrets. Narration scrub drops unsolicited other-PC voluntary acts. Snapshot recovery smoke in `tests/test_play_hardening.py`.
