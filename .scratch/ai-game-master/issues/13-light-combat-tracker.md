# 13: Light Combat Tracker (book-driven)

**What to build:** Campaign State holds an active Combat Encounter (combatants, initiative, turns, optional HP). GM Tools begin/end combat, set initiative, advance turns, apply harm/heal. Procedures come from BookIndex via `lookup_rules`. Vue shows a combat panel. No full combat engine.

**Blocked by:** 12 — Rule consult + Roll Call

**Status:** resolved

- [x] `combat` in EMPTY_STATE / load_state whitelist
- [x] Tools: `begin_combat`, `set_combatant_initiative`, `next_turn`, `apply_harm`, `apply_heal`, `update_combatant`, `end_combat`
- [x] Live prompt injects `combat` + `characters`; off-turn → `not_your_turn`
- [x] Play Application tests cover start, initiative, turn gate, harm, end
- [x] Lobby combat panel + WS patches for combat_* events
- [x] CONTEXT + ADR 0008 + spec revision

## Answer

Light Combat Encounter tracker in Campaign State: book-driven procedures via `lookup_rules`, server-owned dice and HP mutations via GM Tools, Vue panel for round/turn/HP. No full combat engine (ADR 0008).
