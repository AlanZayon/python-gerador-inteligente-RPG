# 4. Generation pipeline

[← RAG](03-rag.md) · [Index](README.md) · [Next: API →](05-api.md)

---

Implemented as `generate_campaign_markdown` in `services/campaign_pipeline.py`, called from `tasks/campaign_tasks.py` after RAG packing.

## Core idea

1. **Plan** the campaign as JSON (Campaign State).
2. **Write** the manuscript in pieces (overview → sessions → appendix).
3. **Score** with a heuristic rubric.
4. **Rewrite** only the weakest section (up to twice).
5. If JSON planning fails entirely → **fallback** to the legacy full prompt (the job still finishes).

## Why this design (not multi-agent)

| Approach | Continuity | Cost | Testability |
|---|---|---|---|
| Single prompt | Weak on long text | Lowest | Easy |
| Outline → expand (legacy) | Expand reinvented the world | Medium | Medium |
| **JSON plan → write → rubric → splice** | Stable names and branches | +1 plan + N sessions + ≤2 revisions | Fake LLM in tests |
| Multi-agent crew | Marginal vs plan+critic | High | Hard |

The critic is **code** (`evaluate_rubric` + `_splice_section`), not a free-form second LLM.

## Campaign State (plan)

The plan is the only place **new names are born**. `normalize_plan` rejects a thin title/premise or too few sessions; coerces string NPCs/factions; fills missing choices from scene approaches; fills approaches to two; splits `Isamu (The Daimyo)` into canonical `name` + `role`.

`plan_is_structurally_complete` checks `COMPLEXITY_SPEC`. `_plan_from_llm` retries once.

> **Evidence (optional):** `docs/evidence/plan-json-excerpt.md`

## Complexity = graph size

| Id | Sessions | NPCs | Factions | Locations | Fronts | Mysteries | Endings | Plan word target | Structural floor |
|---|---|---|---|---|---|---|---|---|---|
| simples | 1–2 | 4 | 2 | 3 | 1 | 0 | 2 | 1,200 | ≥ 800 |
| mediana | 3–4 | 6 | 3 | 5 | 2 | 1 | 3 | 2,800 | ≥ 2,000 |
| complexa | 5–7 | 9 | 4 | 7 | 3 | 2 | 4 | 5,200 | ≥ 4,000 |

## Writing

Overview + hook → one call per session (digest + brief + last three session summaries + extra retrieve) → appendix. `state_digest` (~4.5k chars) is injected every time. Section labels via `campaign_i18n`.

> **Evidence (optional):** `docs/evidence/session-excerpt.md`

## Heuristic rubric

Weighted categories (narrative 1.2, gameplay 1.2, npcs 1.0, world 1.0, content 0.8, consistency 1.3, gm_utility 1.1). Pass: overall ≥ **7.5** and all ≥ **6.0**.

**Consistency** is entity overlap (canonical name / first token ≥ 4 chars), not literary criticism. Parenthetical titles in JSON used to false-fail.

Narrative/gameplay/npcs **saturate** on live runs — useful as a floor, weak as fine ranking.

## Selective revision

Up to two passes while `passed` is false. Rewrites one H2 (overview, NPCs, or session 1 if gameplay is weak) via `_splice_section`.

## User-job hard gate

`validate_campaign` still requires word floor, overview, session headings, NPCs heading, and PC names when sheets were uploaded. Job `quality_score` is 0–100 structural; rubric overall lives in metadata.

## Typical LLM calls

Up to 2 plan attempts + 1 overview + N sessions + 1 appendix + 0–2 revisions. Timeout 600s, 3 retries, 8192 max tokens. Model tier by complexity (`LLM_MODEL_LITE` / `FLASH` / `PRO`).

See also: [Evaluation](07-evaluation.md) · [RAG](03-rag.md) · [Limits](08-limits.md)

---

[← RAG](03-rag.md) · [Index](README.md) · [Next: API →](05-api.md)
