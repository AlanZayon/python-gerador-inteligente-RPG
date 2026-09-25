# 11. Play — overview

[← Voice](10-voice.md) · [Index](README.md) · [Next: GM Runtime →](12-gm-runtime.md)

---

Generation ends in a **Job** (Markdown manuscript + plan). Play starts only when the host explicitly creates a **Campaign** from that Job ([ADR 0001](../adr/0001-campaign-separate-from-job.md)).

## Job ≠ Campaign

| Concept | Role |
|---|---|
| **Job** | Generation history: PDF, legacy credits metadata, S3 keys, async status, persisted Blueprint |
| **Campaign** | Playable instance: Blueprint copy, Character roster, membership, Campaign State |

We rejected overloading Job as the live-play aggregate: it already mixes generation metadata with runtime concerns.

## Blueprint vs Campaign State

| Term | Meaning |
|---|---|
| **Campaign Blueprint** | Durable design (factions, NPCs, locations, fronts, mysteries, manuscript sessions, secrets, endings). Copied onto the Campaign at creation. |
| **Campaign State** | Mutable runtime truth: current scene, NPC flags, progress, inventory/HP if tracked, pending Roll Call, active Combat Encounter. |

The Blueprint is canonical for design; Markdown is a derived presentation. In play, the runtime does not re-parse prose to discover world truth ([ADR 0002](../adr/0002-blueprint-vs-campaign-state.md)).

> In generation chapters, “Campaign State / plan” may still appear as the legacy name for planner JSON. In Play, use **Blueprint** for the plan and **Campaign State** only for runtime.

## Table pieces

| Piece | Definition |
|---|---|
| **GameSession** | Live multiplayer room (lobby → active → ended), with invite and presence |
| **Player** | A seat in a Campaign / GameSession: a User at the table, optionally bound to a Character |
| **Character** | PC on the roster (from sheets at generation). The Player **claims** one Character in the lobby |
| **User** | Clerk account; may hold many Player seats across Campaigns |
| **NPC** | Defined in the Blueprint and/or mutated in Campaign State — not a Character |

## Mental flow

```text
Job completed
    → host creates Campaign (copies Blueprint + knowledge handles)
    → Players join GameSession / lobby
    → each Player claims a Character
    → session active → Game Master Runtime narrates and mutates Campaign State
```

## Where in the code

| Area | Paths |
|---|---|
| Campaigns | `services/play/campaigns.py`, `routes/campaigns.py` |
| Sessions | `services/play/sessions.py`, `routes/sessions.py` |
| WebSocket | `routes/ws_sessions.py`, `services/play/hub.py`, `services/play/sync.py` |
| GM | `services/play/gm/` |

See also: [GM Runtime](12-gm-runtime.md) · [Realtime](15-realtime.md)

---

[← Voice](10-voice.md) · [Index](README.md) · [Next: GM Runtime →](12-gm-runtime.md)
