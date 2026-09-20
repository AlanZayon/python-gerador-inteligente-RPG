# Architecture — Arcane Forge AI Game Master

Phase 0 audit + target architecture. Product decisions are locked in `CONTEXT.md` and `docs/adr/`.

**Repos:** backend `python-gerador-inteligente-RPG` + frontend `pdf-translate-vue` (same product, split repos).

---

## 1. Current architecture

### Processes

| Process | Role today |
|---|---|
| `app.py` (Flask / Gunicorn) | Auth (Clerk JWT), upload, enqueue, job status, dashboard, billing |
| `worker.py` | Redis consumer → `process_campaign_generation` |
| Vue SPA (`pdf-translate-vue`) | Wizard, result, dashboard, pricing/checkout |

### Data & infra

| Layer | Reality |
|---|---|
| DB | PostgreSQL (prod) / SQLite (dev); SQLAlchemy 2; **no Alembic** — `create_all` + ad-hoc `ALTER` |
| Redis | Job queues + job status hashes |
| S3 | Rulebook PDFs, sheet PDFs, campaign Markdown |
| RAG | FAISS on disk + `sentence-transformers` + `book_indexes` |
| LLM | `services/llm_client.py` → 9router OpenAI-compatible `/v1/chat/completions` |
| Auth | Clerk JWT; Studio API key |
| Billing | Stripe, credits, plans, quotas (**to be removed**) |
| Realtime / voice | **None** |

### Domain entities today

| Exists | Meaning |
|---|---|
| `User` | Clerk account + plan/credits |
| `Job` | Async PDF → Markdown unit |
| `BookIndex` | Indexed rulebook (`book_id`) |
| Plan JSON (“Campaign State” in old docs) | **Ephemeral** planner output inside pipeline |
| `character_sheets` on Job | TEXT JSON blob of parsed PCs |
| Campaign (product language) | Finished Markdown manuscript, not a playable world |

**Missing for play:** `Campaign`, `Campaign Blueprint` (persisted), `Campaign State`, `GameSession`, `Player`, `Event`, `Memory`, WebSocket, STT/TTS, GM Runtime.

### Critical operational issue

`models/` is in `.gitignore`. ORM entities are local-only and not versioned. New play schema **must** be tracked in git (stop ignoring domain models or relocate them under a tracked package).

---

## 2. Current generation flow

```text
PDF (S3)
  → validate / extract (PyMuPDF)
  → ensure_indexed (FAISS + BookIndex)
  → optional sheet PDFs → LLM JSON sheets
  → pack_campaign_context (lanes: setting, mechanics, lore, theme)
  → generate_campaign_markdown
        plan JSON → write manuscript → rubric → selective revise
  → validate_campaign hard gate
  → upload .md to S3
  → Job result meta (plan JSON discarded today)
```

Key modules:

- Orchestration: `tasks/campaign_tasks.py`
- Pipeline: `services/campaign_pipeline.py`
- Plan schema: `services/campaign_schema.py` (`normalize_plan`, `PLAN_JSON_INSTRUCTIONS`)
- Rubric: `services/campaign_eval.py`
- Hard gate: `services/campaign_quality.py`
- RAG: `services/rag/*`
- LLM: `services/llm_client.py`

---

## 3. Target architecture (incremental)

Separation of concerns:

```text
CONTENT GENERATION (preserve)          GAME EXECUTION (add)
─────────────────────────────          ────────────────────
Job                                    Campaign
BookIndex / RAG                        Campaign Blueprint
Plan → persist as Blueprint seed       Campaign State
Manuscript (.md)                       GameSession
Sheets on Job → Character roster       Player / Character claim
                                       Event log + Memory
                                       GameMasterRuntime + GM Tools
                                       WebSocket gateway
                                       STT / TTS providers
```

### Target flow

```text
User uploads book + sheets
  → existing pipeline
  → Job SUCCESS + persisted plan JSON + manuscript + sheets
User: Create Campaign
  → Campaign { blueprint copy, book_id, character roster, host }
Host: Create GameSession → invite code
Players (Clerk) join → claim Character
Host Start (all claimed, 2–4)
  → ACTIVE
Player text/voice
  → STT (if voice) → action queue (FIFO, one GM flight)
  → GameMasterRuntime
        context: Blueprint + State + memory(filtered) + RAG + tools
        LLM via 9router
        tools → domain services → DB + events
  → narration (+ TTS) → WebSocket broadcast
```

### Authority

- Server owns dice, state mutations, quest clocks, character updates. PC checks go through a Roll Call; the Player confirms and the server RNG resolves (ADR 0007).
- LLM proposes tool calls and narrates; it is **not** the source of truth.
- GM may know character-private facts; each client/context receives filtered knowledge.

### Concurrency

- One `GameMasterRuntime` flight per `GameSession`.
- Player inputs enter an action queue; processed FIFO.
- Campaign State version / session lock for persistence.

### Realtime

- WebSocket on the Flask API process (single-instance assumption for portfolio).
- Versioned event envelope: `{ version, type, session_id, event_id, payload }`.

### Voice

- Interfaces: `SpeechToTextProvider`, `TextToSpeechProvider`.
- LLM and STT stay on 9router. TTS is provider-selectable: ElevenLabs (`eleven_v3` via official SDK), 9router `/v1/audio/speech`, or mock.
- GameMasterRuntime persists Campaign State, then VoiceDirector renders audio. TTS failure does not roll back the table.
- Speaker identity for STT actions comes from the authenticated connection (`user_id` / `player_id`), not from transcript text.
- See ADR 0006.

---

## 4. Extension points (concrete)

| Concept | Attach here |
|---|---|
| Persist plan on Job success | `tasks/campaign_tasks.py` after `generate_campaign_markdown`; new Job column / S3 key + DB |
| Rename plan language | `services/campaign_schema.py`, docs `04-pipeline`, glossary |
| Create Campaign | New service + routes; copy plan → `campaigns.blueprint_json`; copy sheets → roster |
| GameSession / lobby | New tables + REST; invite code |
| Realtime | Flask-Sock / similar on `app.py`; session gateway module |
| GM Runtime | New package e.g. `services/gm/` — **not** inside `campaign_pipeline.py` |
| RAG reuse | `services/rag/retrieval.py` + packer patterns; scoped queries for GM |
| LLM | Extend `llm_client` (tool calling / routing by purpose) behind same 9router |
| Frontend | New Vue routes: Campaign, Lobby, Game; keep generator wizard |

---

## 5. Problems to address (without big-bang rewrite)

| Issue | Approach |
|---|---|
| Plan discarded | Persist on Job success |
| “Campaign State” name collision | Rename to Blueprint in code/docs |
| No migrations | Introduce Alembic first |
| `models/` gitignored | Track domain models in git |
| Monetization clutter | Delete Stripe/credits/plans/quotas first |
| LLM only chat completions | Add tool-calling path for GM; keep `complete()` for generation |
| Gunicorn multi-worker WS | Document single worker / sticky for WS MVP |
| Sheet extraction weak | Campaign State v1 keeps HP/inventory soft; tools update blobs |

---

## 6. Proposed schema (Phase 1 sketch)

Tables (names indicative):

- `campaigns` — id, job_id, host_user_id, book_id, title, blueprint_json, manuscript_s3_key, status, created_at
- `campaign_characters` — id, campaign_id, sheet_json, display_name, claimable
- `game_sessions` — id, campaign_id, invite_code, status (LOBBY|STARTING|ACTIVE|PAUSED|ENDED), state_json, state_version, current_scene, host_player_id, timestamps
- `session_players` — id, game_session_id, user_id, character_id nullable, role (host|player|spectator), ready, connected
- `game_events` — id, game_session_id, seq, type, actor_id, target_id, payload_json, created_at
- `memories` — id, campaign_id, game_session_id nullable, scope (session|campaign|character_private), character_id nullable, content_json, embedding optional later, created_at

Job change: persist `plan_json` (or S3 pointer) on success.

Do **not** overload `Job` as the live play aggregate.

---

## 7. API / WebSocket sketch

### REST (add)

- `POST /campaigns` from `job_id` (host)
- `GET /campaigns/:id`
- `POST /campaigns/:id/sessions`
- `POST /sessions/join` `{ invite_code }`
- `POST /sessions/:id/claim-character`
- `POST /sessions/:id/ready`
- `POST /sessions/:id/start` (host)
- `POST /sessions/:id/actions` (text fallback)
- `GET /sessions/:id/state` (reconnect snapshot)

### WebSocket events (v1)

Inbound: `player_action`, `player_ready`, `ping`  
Outbound: `player_joined|left`, `character_claimed`, `session_started`, `gm_thinking`, `gm_tool_call`, `gm_narration`, `gm_audio`, `dice_result`, `state_patch`, `error`

---

## 8. Implementation phases

### Phase 0 — Audit (this document) ✅

### Phase 0b — Strip monetization + Alembic foundation

- Remove Stripe/credits/plans/quota gates (backend + Vue)
- Stop ignoring domain models; introduce Alembic
- Keep Clerk + free generation

### Phase 1 — Domain model

- Persist plan JSON on Job success
- Rename plan → Blueprint in pipeline language
- Tables: campaigns, characters, game_sessions, session_players, game_events, memories
- Create Campaign from Job; tests

### Phase 2 — Game runtime (text)

- `GameMasterRuntime`, context builder, tool registry (MVP set)
- Action queue + session lock
- Event log + minimal Campaign State
- Memory layers (session/campaign/character-private) with filter
- Mock LLM for tests

### Phase 3 — Multiplayer

- Lobby, invite, claim, start rules
- WebSocket gateway, presence, reconnect snapshot
- Multi-client tests

### Phase 4 — AI GM live

- Wire 9router tool calling
- RAG retrieval for GM
- Observability (request_id, session_id, tokens, latency)
- Cheap deterministic validation + optional critic for major transitions

### Phase 5 — Voice

- STT/TTS providers + mocks
- Mic → STT → same action queue (identity from connection)
- Narration → TTS → broadcast audio

### Phase 6 — Streaming

- Stream LLM/TTS where providers allow; reduce perceived latency

### Phase 7 — Hardening

- Authz on every tool, rate limits, recovery, cost/latency logs

### Phase 8 — Quality

- GM prompts, rubric, continuity, pacing

---

## 9. Files to create / modify (high level)

### Backend create

- `alembic/` + `alembic.ini`
- Tracked models package (fix `.gitignore` for `models/`)
- `services/campaigns/` — create from job, blueprint copy
- `services/sessions/` — lobby, invite, claim, start
- `services/gm/` — runtime, context, tools, queue
- `services/memory/` — scopes + filter
- `services/voice/` — STT/TTS interfaces + providers
- `routes/campaigns.py`, `routes/sessions.py`
- `realtime/gateway.py` (or `services/realtime/`)
- Docs: `GAME_RUNTIME.md`, `AI_GAME_MASTER.md`, `REALTIME.md`, `VOICE.md`, `DATABASE.md` (as features land)
- Tests under `tests/test_gm_*`, `tests/test_sessions_*`, …

### Backend modify

- `tasks/campaign_tasks.py` — persist plan
- `services/campaign_schema.py` / pipeline docs — Blueprint naming
- `services/llm_client.py` — tool calling + purpose routing
- `app.py` — register blueprints, WS, drop billing
- Delete/gut: `routes/billing.py`, `services/billing.py`, quota plan gates
- `database.py` — hand off schema to Alembic

### Frontend (`pdf-translate-vue`)

- Remove pricing/checkout/upgrade/usage meter tied to billing
- Result page: **Create Campaign** CTA
- New pages: Campaign, Lobby, Game (text first, then mic/TTS)
- Auth stays Clerk

---

## 10. Non-goals (v1)

Maps/tokens/VTT clone, payments, native apps, full rules DSL, multi-instance WS cluster, parallel GameSessions per Campaign, spectator UX polish.

---

## 11. Definition of done (product)

Matches locked decisions: generation preserved → Create Campaign → invite 2–4 → claim characters → text+voice play → authoritative dice/state → events persisted → server restart recoverable → tests/lint green.
