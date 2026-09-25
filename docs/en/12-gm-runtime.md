# 12. Game Master Runtime

[← Play](11-play-overview.md) · [Index](README.md) · [Next: Roll Call →](13-roll-call.md)

---

The **Game Master Runtime** is the application loop that turns player intent + Blueprint + Campaign State + memory + rules retrieval into GM decisions, **GM Tool** calls, narration, and state updates.

It is not a chatbot: the model suggests and narrates; server tools are the source of truth for dice, HP, and mutations.

## Inputs and outputs

```text
Player action (text / voice STT)
    → context: Blueprint digest, Campaign State, allowed memories, RAG pack
    → LLM (9router) + tool calls
    → GM Tools run on the server
    → Campaign State / events saved
    → public narration (+ optional Voice Direction → TTS)
```

## GM Tools (authority)

Specs live in `services/play/gm/tools.py`. Examples:

| Tool | Role |
|---|---|
| `lookup_rules` | Search the BookIndex before a PC check |
| `request_roll` | Issue a Roll Call (does not roll) — see [Roll Call](13-roll-call.md) |
| `roll_dice` / `perform_check` | Hidden GM/NPC rolls only |
| `read_world_state` / `update_world_state` | Read / patch Campaign State |
| `create_event` | Append a game event |
| combat tools | `begin_combat`, `apply_harm`, `next_turn`, … — see [Combat](14-combat.md) |

Tool results are authoritative. The model must **not** invent dice totals or HP when a tool exists.

## Character-private knowledge

World truths may be known only to a Character (or subset). The GM (server) may know everything; each player only receives what their Character is allowed to know. Do not treat public/shared memory as the default.

## Voice after state

The voice layer (Narration → Voice Director → TTS) runs **after** Campaign State is saved. Voice Direction (Audio Tags such as `[whispers]`) never changes rules, inventory, combat, or quests. Ops detail: [Voice](10-voice.md).

## Where in the code

| Piece | Path |
|---|---|
| Runtime / actions | `services/play/gm/runtime.py`, `actions.py` |
| Live / mock LLM | `live_llm.py`, `mock_llm.py` |
| State | `state.py` |
| Play RAG | `rag_context.py` |
| Tools | `tools.py` |

---

[← Play](11-play-overview.md) · [Index](README.md) · [Next: Roll Call →](13-roll-call.md)
