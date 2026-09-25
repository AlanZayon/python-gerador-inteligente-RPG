# 12: Rule consult + Roll Call

**What to build:** GameMasterRuntime can look up BookIndex passages on demand (`lookup_rules` in a short tool loop), then issue a Roll Call (`request_roll`) instead of rolling PC dice immediately. The targeted Player confirms; the server RNG resolves; a second flight narrates the outcome.

**Blocked by:** 08 — Live 9router GM + RAG

**Status:** resolved

- [x] `lookup_rules` is a GM Tool; tool loop executes lookups before mutations (max 3 rounds)
- [x] Seed retrieval is mechanics-biased; turn context includes `system_preset` and the acting Character sheet
- [x] `request_roll` persists `pending_check` and emits `roll_requested` without rolling
- [x] Other player actions fail with `awaiting_roll` while a Roll Call is pending
- [x] `confirm_roll` is Play Application + HTTP + WebSocket; only the targeted Character’s Player may confirm
- [x] Resolution flight narrates from server dice; v1 does not issue another Roll Call
- [x] Hidden GM/NPC rolls may still use `roll_dice` immediately
- [x] Vue shows a Roll Call card, blocks action input, and displays dice detail
- [x] Play Application tests cover lookup scope, pending state, permissions, reconnect, and resolution

## Answer

PC checks are now a two-flight ritual: `lookup_rules` (tool loop) → `request_roll` / `pending_check` → targeted Player confirms → server `DiceRng` → `roll_resolution` narration. Hidden GM/NPC rolls still use `roll_dice` immediately (ADR 0007).
