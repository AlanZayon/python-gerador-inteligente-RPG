# Campaign generation architecture

This document records why the generator changed from a single (or outline→expand) prompt into a **plan → write → score → revise** pipeline, and how to judge whether a campaign is good enough.

## Current production flow

```
PDF
  → fingerprint + FAISS index (reused when the same book returns)
  → coverage retrieval (setting / mechanics / lore / theme)
  → context packing (token floor/ceiling, lane coverage, key terms)
  → optional system heuristic (GURPS, Blood & Honor, Fragged, D&D, …)
  → JSON campaign plan (Campaign State)
  → overview + per-session writing + appendix (state digest injected every time)
  → structural validator (headings, session count, word floor, book terms)
  → quality rubric (7 categories, 0–10)
  → selective section revision (bounded)
  → markdown normalize + S3
```

If the plan is not valid JSON, the pipeline **falls back** to the previous full-manuscript prompt so jobs still complete.

## Why this architecture (not multi-agent)

| Option | Quality | Cost / latency | Ops |
|---|---|---|---|
| One-shot prompt | Weak long-range consistency | Lowest | Simplest |
| Outline → expand (old) | Better, but expand still reinvented the world | Medium | Current |
| Plan JSON → incremental write → rubric → splice | Strong names/continuity; complexity = more graph, not more filler | +1 plan call, +N session calls | Same worker, same 9router |
| Full multi-agent crew | Marginal vs plan/write/critic | High | Hard to test |

We implemented the third option. Agents with extra roles would duplicate the critic already expressed as a **deterministic rubric + targeted rewrite**.

## Campaign State

The plan is the only place new names should be born. Later prompts receive `state_digest(...)`: title, premise, thematic question, conflict, stakes, factions, NPCs (want/secret/quirk), locations, fronts, mysteries with clues, session list, endings.

Complexity (`simples` / `mediana` / `complexa`) changes **minimum graph size** (sessions, factions, fronts, clues, endings), not just word count.

## Quality rubric

Categories (weighted): narrative, gameplay, NPCs, world, content, consistency, GM utility.

- Pass: overall ≥ **7.5 / 10** and every category ≥ **6.0**
- Structural validator remains a hard gate for the user-facing job
- Rubric drives selective revision; `quality_score` on the job is still 0–100 (structural), with `rubric` in generation metadata

## RAG

Unchanged chunking (500–800 tokens, 100 overlap). Mechanics queries now exist for GURPS, Blood & Honor, and Fragged Empire, not only D&D/PF/CoC. After packing, if the user left the preset on generic, a **heuristic** may re-pack with the detected system's mechanics query.

## Reference books (local PDFs, used as systems—not copy-paste modules)

| Book | What we test |
|---|---|
| Blood & Honor | Tragedy, honor, clan/court, social risk |
| D&D 5e 2024 PHB | Checks, rest, encounters, original setting using those rules |
| GURPS Lite 4e | 3d6, advantages, genre flexibility |
| Fragged Empire | Post-collapse sci-fi factions, resources, identity |

## Known limits

- Session writers can still drift if the model ignores the digest; the rubric penalizes missing planned names but cannot prove lore correctness against the PDF.
- Key terms are still mostly capitalized tokens; dense all-caps or uncapitalized setting names are under-detected.
- Live 12-book×complexity runs need 9router and minutes-to-hours; `scripts/eval_reference_campaigns.py` is the harness.
- Portuguese/English heading mix is handled by i18n detectors, not by the rubric.

## Future work

- Tight JSON schema validation (enum fields) on the plan
- Per-lane recency / page metadata in FAISS
- Optional second-pass LLM critic only for `complexa`
- Store Campaign State beside the markdown for later section regen
