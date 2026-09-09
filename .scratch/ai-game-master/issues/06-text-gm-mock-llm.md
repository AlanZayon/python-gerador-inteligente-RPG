# 06: Text GM turn with mock LLM

**What to build:** In an ACTIVE GameSession, a Player submits a text action. It enters a FIFO per-session queue; a single GameMasterRuntime flight runs with a mock LLM, uses MVP tools (dice, checks, world/character/quest updates, events), updates minimal Campaign State, and returns public narration—without inventing dice when a tool exists.

**Blocked by:** 05 — GameSession lobby (invite → claim → start)

**Status:** resolved

- [x] Text actions are accepted only from session members controlling their Character
- [x] Concurrent actions serialize via FIFO; only one GM flight runs at a time
- [x] MVP tools persist results and emit game events; Campaign State updates are durable
- [x] Mock LLM path is the default in tests; no 9router required for green CI
- [x] Minimal Campaign State surface works (scene/location, NPC flags, simple clocks, notes, last dice)
- [x] Play Application tests prove tool-authoritative dice and two rapid actions do not corrupt state
