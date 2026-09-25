# 14. Combat tracker

[← Roll Call](13-roll-call.md) · [Index](README.md) · [Next: Realtime →](15-realtime.md)

---

Table combat is a **light tracker** in Campaign State — not a compiled multi-system engine ([ADR 0008](../adr/0008-light-combat-tracker.md)).

Procedures (how to roll initiative, attack, damage, death) come from the **BookIndex** via `lookup_rules` and LLM interpretation. The server owns dice and persists tracker mutations.

## What the tracker stores

| Field | Notes |
|---|---|
| Combatants | PC (linked to Character) or NPC (encounter-only) |
| Initiative / order | Turn order |
| Turn pointer | Whose turn it is |
| HP / resources / status | Optional — tags and numbers, not a rules DSL |

## Combatant ≠ Character

- **Character** — PC on the Campaign roster.
- **Combatant** — a row in the encounter (name, side, initiative, hp…); NPCs live only here during the fight.

## Typical tools

Mutations go through GM Tools, e.g. `begin_combat`, `apply_harm`, `next_turn`, … (see `services/play/gm/tools.py` and `combat.py`).

PC combat rolls use **Roll Call**, not immediate `roll_dice`.

## What was rejected

- A full rules DSL or hard-coded hit-vs-AC pipeline in Python (would block arbitrary uploaded systems).
- Treating narration / Voice Direction as HP authority.

Voice Direction must **never** mutate combat or Campaign State.

## Distinct from the manuscript

“Combat:” sections in the Blueprint / Markdown are session design. An active **Combat Encounter** is runtime Campaign State.

Implementation: `services/play/gm/combat.py`.

---

[← Roll Call](13-roll-call.md) · [Index](README.md) · [Next: Realtime →](15-realtime.md)
