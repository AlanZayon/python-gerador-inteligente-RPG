# Arcane Forge — AI Game Master

Personal / portfolio platform: upload a rulebook and character sheets, generate a campaign, then play it online with friends via Clerk, WebSocket, and voice. Not a commercial product — billing, credits, plans, and Stripe are out of scope and to be removed.

## Language

### Generation (onboarding pipeline)

**Job**:
One async generation unit: rulebook PDF + params (+ optional sheets) → Markdown manuscript and structured plan data. A Job is not playable until the host explicitly creates a Campaign from it.
_Avoid_: Campaign (for the generation artifact alone)

**Campaign Blueprint**:
The durable structured design of a campaign (formerly “Campaign State” / plan JSON): factions, NPCs, locations, fronts, mysteries, manuscript sessions, secrets, endings. Copied onto the Campaign when the host chooses to play.
_Avoid_: Campaign State (for the plan), plan (as the product name)

**Manuscript Session**:
A planned chapter in the Blueprint / Markdown (`Session N`). Not a live multiplayer room.
_Avoid_: Session (unqualified), GameSession

**BookIndex**:
Indexed rulebook identity used by RAG (`book_id`, fingerprint, embeddings).
_Avoid_: Rulebook (as a DB table name unless introduced later)

### Play (runtime)

**Campaign**:
A playable world instance seeded from a completed Job (Blueprint + knowledge handles + membership). The thing players join.
_Avoid_: Job (once play has started)

**Campaign State**:
Mutable runtime truth of what has happened in play (NPC status, quest progress, relationships, inventory/HP if tracked, current scene). Distinct from the Blueprint.
_Avoid_: Blueprint, World State (prefer this term unless a narrower synonym is needed)

**GameSession**:
A live multiplayer room for a Campaign (lobby → active → ended), with invite and presence.
_Avoid_: Session (unqualified), Stripe session, browser session

**Player**:
A seat in a Campaign / GameSession: a User participating at the table, optionally bound to a Character.
_Avoid_: User (when meaning the seat), Character

**Character**:
A player character on the Campaign roster (from sheets uploaded at generation). A Player **claims** one Character in the lobby. Not an NPC.
_Avoid_: Player, NPC

**User**:
A Clerk-authenticated account. May hold many Player seats across Campaigns.
_Avoid_: Player

**NPC**:
A non-player character defined in the Blueprint and/or mutated in Campaign State.

**Character-private knowledge**:
Campaign memory that is true in the world but only known to a specific Character or subset of Characters. The GM may know it; players only receive what their Character is allowed to know.
_Avoid_: public memory, shared memory

### AI / authority

**Game Master Runtime**:
The application loop that turns player intent + Blueprint + Campaign State + memory + rules retrieval into GM decisions, tool calls, narration, and state updates.
_Avoid_: chatbot, LLM alone as source of truth

**GM Tool**:
A server-side capability the GM agent may invoke (dice, state updates, retrieval). Results are authoritative; the model does not invent dice/HP outcomes when a tool exists.

### Voice

**Narration**:
Voice-layer object (speaker, table text, optional Voice Direction) sent to the Voice Director after Campaign State is already saved. Distinct from the GM's public table-narration string.
_Avoid_: treating TTS audio as game authority

**Voice Direction**:
Audiovisual delivery hints (Audio Tags such as `[whispers]`). Never changes rules, Campaign State, inventory, combat, or quests.
_Avoid_: mapping tags to game logic

**Voice Profile**:
Configured mapping from speaker name (`gm`, `villain`, …) to an ElevenLabs `voice_id`. Unknown speakers fall back to the GM profile.
_Avoid_: scattering raw voice IDs through Game Master code

**Voice Director**:
Turns Narration into provider input (resolve speaker, apply Audio Tags, call TTS). Does not know RPG rules.
