# AI Game Master — Multiplayer Real-Time RPG

Status: ready-for-agent

## Problem Statement

I can upload a rulebook and character sheets and get a generated campaign manuscript, but I cannot actually play that campaign with friends. There is no live table, no AI Game Master that respects durable game truth, no multiplayer lobby, and no voice. Monetization (Stripe, credits, plans) also gets in the way of a personal/portfolio build.

## Solution

Keep the existing generation pipeline as onboarding. When a Job finishes, persist its structured plan. I explicitly create a Campaign from that Job, invite 2–4 friends via Clerk, each claims a Character, and we play in a GameSession where an AI Game Master narrates, calls tools, and updates authoritative Campaign State. Text and voice both work; dice and state changes are server-owned; billing is removed.

## User Stories

1. As a host, I want to upload a rulebook PDF, so that the system can index rules and lore for generation and later GM retrieval.
2. As a host, I want to upload character sheets with the rulebook, so that the party roster exists before play.
3. As a host, I want generation to still produce a Markdown manuscript, so that I can read the adventure as a document.
4. As a host, I want the planner JSON to be persisted when a Job succeeds, so that play does not depend on re-parsing the manuscript.
5. As a host, I want an explicit “Create Campaign” action on a successful Job, so that not every generation becomes a live table by accident.
6. As a host, I want creating a Campaign to copy the Campaign Blueprint onto the Campaign, so that design is durable and separate from runtime.
7. As a host, I want creating a Campaign to copy extracted sheets into a Character roster, so that players can claim seats.
8. As a host, I want the Campaign to remember the BookIndex / book identity, so that the GM can retrieve rules later.
9. As a host, I want to create a GameSession for my Campaign, so that friends can gather in a lobby.
10. As a host, I want an invite code, so that friends can join without a complex sharing UI.
11. As a player, I want to join a GameSession with an invite code while signed in with Clerk, so that my identity is stable.
12. As a player, I want to see the available Characters in the roster, so that I know what I can claim.
13. As a player, I want to claim exactly one unclaimed Character, so that each seat maps to one PC.
14. As a host, I want Start to be blocked until every Player has claimed a unique Character and the table size is between 2 and 4, so that play begins with a valid party.
15. As a host, I want only one active GameSession per Campaign, so that Campaign State does not fork.
16. As a player, I want to mark myself ready, so that the host knows the lobby is set.
17. As a host, I want to start the GameSession, so that we move from lobby to active play.
18. As a player, I want to send a text action, so that I can play without a microphone.
19. As a player, I want to hold-to-speak (or equivalent) and have my speech transcribed, so that I can act by voice.
20. As the system, I want speaker identity to come from the authenticated connection, so that voice cannot impersonate another Player by transcript content alone.
21. As a player, I want my action to enter a per-GameSession FIFO queue, so that simultaneous inputs do not corrupt state.
22. As the system, I want only one GameMasterRuntime flight at a time per GameSession, so that tools and state updates stay serialized.
23. As a player, I want the GM to see the Campaign Blueprint, so that NPCs, locations, fronts, and secrets stay coherent with the design.
24. As a player, I want the GM to see Campaign State, so that what already happened is not forgotten or contradicted.
25. As a player, I want the GM to retrieve relevant rulebook passages via existing RAG, so that rulings can cite the uploaded book without stuffing the whole book into context.
26. As a player, I want the GM to use tools instead of inventing dice results, so that rolls are trustworthy.
26a. As a player, I want the GM to look up rulebook mechanics on demand during a turn, so that it can decide whether a check is required.
26b. As a player, I want a PC check to become a Roll Call I confirm in the UI, so that I authorize the roll before the server RNG resolves it.
26c. As a player, I want hidden GM/NPC rolls to resolve immediately via `roll_dice`, so that secret rolls are not blocked on my click.
27. As a player, I want `perform_check` / dice tools to persist results and emit events, so that outcomes are auditable.
28. As a player, I want the GM to update Campaign State through tools (scene, NPC flags, clocks), so that the world is server-authoritative.
29. As a player, I want the GM to update Character fields through tools when applicable, so that HP/inventory-like data is not hallucinated when tracked.
30. As a player, I want quest/front progress updated through tools, so that advancement is explicit.
31. As a player, I want important happenings stored as game events, so that we can reconstruct what occurred.
32. As a player, I want session memory and campaign memory, so that the GM retains decisions beyond raw chat history.
33. As a player, I want character-private knowledge, so that secrets my Character learned are not auto-revealed to others.
34. As the GM Runtime, I want to know all truths needed for continuity, while each Player only receives narration/context filtered to their Character, so that privacy and continuity both hold.
35. As a player, I want GM narration broadcast to the table, so that everyone hears/sees the same public outcome.
36. As a player, I want GM narration spoken via TTS, so that the table feels like a live GM.
37. As a player, I want reconnect after refresh or network drop to restore Campaign State and missed events, so that play survives flaky connections.
38. As a host, I want GameSession status transitions (lobby → active → paused/ended) to be clear, so that I know whether we can act.
39. As a developer, I want billing, credits, plans, Stripe, and pricing UI removed, so that the portfolio project is not cluttered with monetization.
40. As a developer, I want generation to remain free/unblocked by quotas tied to plans, so that personal use stays simple.
41. As a developer, I want Clerk auth retained, so that multiplayer identity still works.
42. As a developer, I want schema changes via Alembic, so that Campaign/GameSession tables are reviewable and recoverable.
43. As a developer, I want domain models tracked in version control, so that clones are not missing ORM entities.
44. As a developer, I want a mock LLM provider for tests, so that GameMasterRuntime can be tested without spending on 9router.
45. As a developer, I want mock STT/TTS providers, so that voice paths are testable offline.
46. As a developer, I want LLM calls for the GM to go through the existing 9router integration, so that we do not invent a parallel model stack.
47. As a developer, I want STT/TTS to be separate providers from 9router, so that audio does not depend on chat-completions alone.
48. As a player, I want the GM not to decide my Character’s voluntary actions, so that player agency is preserved.
49. As a host, I want the Markdown manuscript to remain available as a reading artifact, while Blueprint stays canonical for play, so that edits to prose do not silently redefine the live world.
50. As a developer, I want structured logs with session/request correlation for GM and tool calls, so that I can debug play sessions.
51. As a player, I want presence updates when someone joins or leaves, so that the lobby/table feels shared.
52. As a host, I want to end a GameSession, so that the Campaign can later start another session without parallel active rooms.
53. As a developer, I want Campaign State to stay narrative-first (scene/location, NPC flags, clocks, notes, last dice, Roll Call) plus a light Combat Encounter tracker, so that we ship authoritative dice without a full multi-system combat engine.
54. As a portfolio visitor / operator, I want a text-first path that still works if voice is misconfigured in local setup, so that demos degrade gracefully—while voice remains part of the product definition of done.

## Implementation Decisions

- Product is personal/portfolio: remove Stripe, credits, paid plans, pricing/checkout UI, and plan-tied quotas from backend and frontend; keep Clerk.
- Preserve the generation pipeline (book → RAG → sheets → plan → write → rubric → manuscript). Do not rewrite it.
- On Job success, persist the planner JSON (Blueprint seed). Creating a Campaign copies that JSON into the Campaign’s Campaign Blueprint.
- Rename the old pipeline term “Campaign State” (meaning the plan) to Campaign Blueprint in product language and new code; Campaign State means runtime truth only.
- Campaign is a new aggregate seeded from Job; Job is not the live-play aggregate (ADR 0001).
- Blueprint is canonical for play; manuscript is derived presentation (ADR 0002).
- Introduce Alembic; stop relying on ad-hoc `create_all` / manual ALTER for new schema; track domain models in git (ADR 0003).
- Strip monetization before growing the play schema (ADR 0004).
- GameSession statuses: at least LOBBY, STARTING, ACTIVE, PAUSED, ENDED; at most one ACTIVE GameSession per Campaign.
- Lobby rules: 2–4 Players; Start requires every Player to have claimed a unique Character from the generation roster.
- Realtime: WebSocket on the API process; single-instance / sticky assumption for MVP (ADR 0005). Persist authoritative state and events in DB for reconnect/restart.
- Concurrency: per-GameSession action queue, FIFO; single GameMasterRuntime flight at a time.
- LLM: reuse 9router via the existing client abstraction; extend for GM tool calling and purpose-based model routing as needed.
- STT/TTS: provider interfaces with real implementations separate from 9router; mocks for tests.
- GM tools MVP: `lookup_rules`, `request_roll`, `roll_dice`, `perform_check`, `read_world_state`, `update_world_state`, `create_event`, `update_character`, `update_quest`, plus light combat tools (`begin_combat`, `set_combatant_initiative`, `next_turn`, `apply_harm`, `apply_heal`, `update_combatant`, `end_combat`).
- PC checks: consult BookIndex → Roll Call in Campaign State → targeted Player confirms → server `DiceRng` → resolution narration. Hidden GM/NPC rolls may use `roll_dice` immediately (ADR 0007).
- Rules ambition v1: narrative GM + authoritative dice + light Combat Encounter tracker; no full multi-system combat engine (ADR 0008). Procedures from BookIndex via `lookup_rules`.
- Memory: session memory, campaign memory, and character-private knowledge; GM may know all; Player-facing context is filtered.
- Play Application boundary is the primary module under test (create Campaign, session lobby lifecycle, submit player action, reconnect snapshot). HTTP and WebSocket are thin adapters over that boundary.
- Frontend MVP surfaces: keep generator; add Create Campaign; Lobby; Game (narration, players, text input, mic, session events).
- Observability: correlate session_id / request_id / tool / model / latency / token usage for GM calls where available.
- Phased delivery order remains: strip monetization + Alembic → domain model → text GameMasterRuntime → multiplayer WS → live 9router GM → voice → streaming → hardening → quality.

### Locked behavioral shapes (from design grill)

GameSession lifecycle (conceptual):

```text
LOBBY → STARTING → ACTIVE ⇄ PAUSED → ENDED
```

Player action processing (conceptual):

```text
input (text | STT text)
  → identify Player from auth
  → enqueue
  → GameMasterRuntime (exclusive)
  → tools (lookup_rules loop → request_roll | mutations)
  → Campaign State + events + memory
  → narration (+ TTS)
  → broadcast
```

PC Roll Call (conceptual):

```text
GM flight: lookup_rules? → request_roll → pending_check → narrate the call
  → other actions rejected (awaiting_roll)
Player confirm
  → server DiceRng → last_dice, clear pending
  → resolution flight → narrate outcome
```

Light Combat Encounter (conceptual):

```text
lookup_rules (initiative / attack / damage from book)
  → begin_combat → set initiatives (Roll Call / roll_dice)
  → turn loop: on-turn action → request_roll | roll_dice → apply_harm/heal → next_turn
  → end_combat
Off-turn PC actions → not_your_turn (confirm_roll still allowed for pending target)
```

## Testing Decisions

- Good tests assert external behavior of the Play Application boundary: given durable fixtures (Job with persisted Blueprint seed + sheets), exercising use cases yields expected Campaign/GameSession/Campaign State/events/narration/errors—not internal prompt strings or ORM call sequences.
- Prefer one seam: the Play Application boundary with injectable LLM, STT, TTS, and dice RNG.
- Do not make WebSocket protocol or Vue components the primary seam; adapters may have thin smoke tests later.
- Generation regression: existing pipeline tests remain the prior art; add assertions that successful generation persists Blueprint seed data without breaking manuscript output.
- Mock LLM/STT/TTS in unit/integration tests (prior art: fake LLM and mock Redis in current pytest suite).
- Cover: Create Campaign from Job; invite join; claim conflicts; Start gate (count + claims); FIFO serialization of two rapid actions; tool-driven dice not inventable by mock “LLM claim”; character-private memory not leaked into another Player’s filtered context; reconnect snapshot after state change; authorization failures (non-member, non-host start).
- Multiplayer safety: simulate at least two Players against the application boundary (not necessarily two browsers) for queue and claim rules.

## Out of Scope

- VTT features: maps, tokens, 3D, fog of war
- Marketplace, social network, payments, native mobile/desktop apps
- Full rules DSL / compiling arbitrary systems into a combat engine
- Parallel active GameSessions / forked timelines per Campaign
- Spectator polish as a first-class UX (hard Start rules preferred)
- Replacing FAISS/RAG stack or replacing 9router for chat/GM LLM
- Microservices, Kafka, full event sourcing framework
- AI-generated maps/images/music
- Making manuscript edits auto-sync into Blueprint

## Further Notes

- Domain vocabulary lives in `CONTEXT.md`; architecture overview in `ARCHITECTURE.md`; ADRs 0001–0007 record irreversible product/architecture choices.
- Backend and Vue are split repos of one product; monetization removal and play UI span both.
- Voice is part of definition of done for the portfolio story, but text path must work throughout development.
- Old docs/glossary still say “Campaign State” for the plan JSON; implementers must treat that as legacy naming for Campaign Blueprint.
