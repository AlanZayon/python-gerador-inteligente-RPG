# 5. Quality pipeline (plan → write → revise)

`generate_campaign_markdown` in `services/campaign_pipeline.py`, invoked from `tasks/campaign_tasks.py` after packing.

## 5.1 Why not multi-agent

A JSON plan plus a **deterministic rubric** and a bounded splice-rewrite beats a crew of extra LLM roles on testability and cost. Agents would duplicate the critic already expressed in code.

## 5.2 Campaign State

The plan is the only place **new names are born**. `normalize_plan` rejects a thin title/premise or too few sessions; coerces string NPCs/factions; fills missing choices from scene approaches; fills approaches to two; splits `Isamu (The Daimyo)` into canonical `name` + `role`.

`plan_is_structurally_complete` checks `COMPLEXITY_SPEC`. `_plan_from_llm` retries once. A valid but incomplete plan may still be used. If JSON fails entirely: `pipeline = fallback-full` (legacy single prompt). The job still finishes.

> **Evidence — plan excerpt**  
> Expected path: `docs/evidence/plan-json-excerpt.md`

## 5.3 Writing

Overview + hook → one LLM call per session (digest + brief + last three session summaries + extra retrieve) → appendix. Section titles via `campaign_i18n`. `state_digest` (~4.5k chars) is injected every time.

> **Evidence — one session**  
> Expected path: `docs/evidence/session-excerpt.md`

## 5.4 Heuristic rubric

Weighted categories (narrative 1.2, gameplay 1.2, npcs 1.0, world 1.0, content 0.8, consistency 1.3, gm_utility 1.1). Pass: overall ≥ **7.5** and all ≥ **6.0**.

**Consistency** is entity overlap (canonical name / first token ≥ 4 chars), not literary criticism. Parenthetical titles in JSON used to false-fail (4.5 with a coherent manuscript).

Narrative/gameplay/npcs **saturate** on live runs — good as a floor, weak as a ranking.

## 5.5 Selective revision

Up to two passes while `passed` is false. Rewrites one H2 (overview, NPCs, or session 1 if gameplay is weak) via `_splice_section`.

## 5.6 User-job hard gate

`validate_campaign` still requires word floor, overview, session headings, NPCs heading, and PC names when sheets were uploaded. Job `quality_score` is 0–100 structural, not rubric×10 (though `rubric_as_100` is stored in metadata).

## 5.7 Typical LLM calls

Up to 2 plan attempts + 1 overview + N sessions + 1 appendix + 0–2 revisions. Timeout 600s, 3 retries, 8192 max tokens, model tier by complexity (`LLM_MODEL_LITE|FLASH|PRO`).
