# 08: Live 9router GM + RAG

**What to build:** GameMasterRuntime can call the real 9router (tool calling) instead of only the mock, with scoped rulebook retrieval from the existing RAG stack. Tests continue to use the mock; live mode is configurable. GM context includes Blueprint, Campaign State, and retrieved rules without stuffing the whole book.

**Blocked by:** 06 — Text GM turn with mock LLM

**Status:** resolved

- [x] Live GM turns use the existing 9router integration (no parallel LLM stack)
- [x] Tool calls from the model are validated and executed via the same tool services as the mock path
- [x] RAG retrieval is scoped (scene/character/query)—not full-book injection
- [x] Mock provider remains selectable for tests and local demos without keys
- [x] Basic observability fields exist for purpose/model/latency (tokens when available)
- [x] Contract tests cover invalid tool calls / malformed model output handling
