# 09: Memory (session / campaign / character-private)

**What to build:** The GM persists session and campaign memories beyond raw chat history, plus character-private knowledge. The Runtime may know private facts for continuity; each Player’s filtered context and public narration do not leak another Character’s secrets.

**Blocked by:** 06 — Text GM turn with mock LLM

**Status:** resolved

- [x] Session and campaign memories can be written and read across turns
- [x] Character-private memories are stored with Character scope
- [x] Filtered context for Player A does not include B’s private knowledge
- [x] Public narration path does not auto-reveal private secrets to the whole table
- [x] Play Application tests cover a private discovery + second Player context/narration filter
