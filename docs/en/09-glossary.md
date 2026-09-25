# 9. Glossary

[← Limits](08-limits.md) · [Index](README.md) · [Play →](11-play-overview.md)

---

| Term | Meaning in this repository |
|---|---|
| **Job** | One async unit: PDF + params → one Markdown |
| **Campaign State / plan** | Canonical JSON; source of names |
| **Digest** | Truncated textual render of state for writer prompts |
| **Lane** | One of four retrieval queries |
| **Packing** | Chunk selection under a token budget |
| **Preset** | System id that switches mechanics query + prompt block |
| **Rubric** | Heuristic 0–10 scores in seven categories |
| **Hard gate** | `validate_campaign` for user-facing success |
| **9router** | Local OpenAI-compatible gateway |
| **book_id** | `bk_` + 16 hex of SHA-256 (or Hamming reuse) |
| **simples / mediana / complexa** | Campaign **graph** size, not a quality adjective |
| **Front** | Off-screen pressure (impulse, portents, doom) |
| **Fallback-full** | Legacy single prompt when JSON planning fails |
| **Ack** | `LREM` of the job from `rpg:processing_jobs` after terminal success or failure |
| **Voice Director** | Turns table narration into TTS input (speaker, Audio Tags); not game rules |
| **Voice Profile** | Speaker name → ElevenLabs `voice_id` |
| **Campaign Blueprint** | Durable campaign design (planner JSON); copied onto the Campaign at creation |
| **Campaign** | Playable instance created from a completed Job |
| **Campaign State** | Mutable runtime truth in play (scene, flags, Roll Call, combat) — distinct from Blueprint |
| **GameSession** | Live multiplayer room (lobby → active → ended) |
| **Player** | Seat at the table (User + optional Character) |
| **Character** | PC on the roster; claimed in the lobby |
| **Roll Call** | GM request that a Character confirm a check; server RNG after Player authorizes |
| **Combat Encounter** | Light combat tracker in Campaign State |
| **Combatant** | PC/NPC row in the encounter (do not confuse Character with NPC) |
| **Game Master Runtime** | Loop intent → tools → narration → state |
| **GM Tool** | Server-side capability the GM agent may invoke |
| **BookIndex** | Indexed rulebook identity (`book_id`, embeddings) used in play via `lookup_rules` |

Play: [overview](11-play-overview.md) · [GM Runtime](12-gm-runtime.md) · [Roll Call](13-roll-call.md) · [Combat](14-combat.md) · [Realtime](15-realtime.md)

---

[← Realtime](15-realtime.md) · [Index](README.md)
