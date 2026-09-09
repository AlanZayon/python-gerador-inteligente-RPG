# 03: Persist Campaign Blueprint seed on Job success

**What to build:** When a generation Job succeeds, the planner JSON (Campaign Blueprint seed) is persisted with the Job alongside the manuscript. Generation quality and manuscript output remain intact; Create Campaign can later copy this seed without re-parsing Markdown.

**Blocked by:** 02 — Alembic + tracked domain models

**Status:** resolved

- [x] Successful Jobs store the normalized planner JSON (Blueprint seed) durably
- [x] Manuscript upload/result behavior still works as before
- [x] Failed or fallback-full paths are defined (seed absent or partial) without crashing the Job
- [x] Pipeline/regression tests cover persistence of the seed on the happy path
- [x] Product language treats this artifact as Blueprint seed, not runtime Campaign State
