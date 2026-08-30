# 7. Evaluation

[← Operations](06-operations.md) · [Index](README.md) · [Next: Limits →](08-limits.md)

---

Two quality layers. Do not conflate them.

| Layer | Code | Role |
|---|---|---|
| Structural | `validate_campaign` | User jobs: headings, sessions, word floor |
| Heuristic | `evaluate_rubric` | Pipeline + matrix: seven axes, floor 6.0 / overall 7.5 |

## Matrix script

`scripts/eval_reference_campaigns.py`

| Mode | Output |
|---|---|
| Dry-run (no LLM) | `examples/eval_runs/reference_matrix.json` (fixtures) |
| `--live --resume` | Local Markdown + `live_matrix.json` |

Reference books (gitignored at repo root): Blood & Honor, 5e 2024 PHB, GURPS Lite 4e, Fragged Empire. Themes are pinned in the script.

```bash
.\venv\Scripts\python.exe scripts\eval_reference_campaigns.py --live --resume
```

## Live matrix (canonical name matching)

Local eval session. Not a literary grade.

| Book | simples | mediana | complexa |
|---|---|---|---|
| Blood & Honor | 8.94 · cons 6.5 | 9.33 · cons 7.0 | 9.35 · cons 7.0 |
| D&D 5e | 9.00 · cons 6.0 | 9.09 · cons 6.5 | 9.32 · cons 7.0 |
| GURPS | 9.39 · cons 7.0 | 9.39 · cons 7.0 | 9.29 · cons 7.0 |
| Fragged | 9.31 · cons 6.5 | 9.21 · cons 6.0 | 9.40 · cons 7.0 |

Mean overall ~**9.25**. Worst cell **8.94**. All `passed=true` on this rubric. Weakest axis: **consistency** at the floor.

Before canonical matching, 6/12 failed consistency only while names were already in the prose.

> **Evidence (optional):** `docs/evidence/eval-matrix.png` · `docs/evidence/rubric-report.md`

## What the metric proves and does not prove

| Proves | Does not prove |
|---|---|
| Playable structure (sessions, NPCs, signaled choices) | Rule correctness vs the PDF |
| Reuse of plan names | Literary quality / real table play |
| Rough absence of generic tropes | That every new book will score the same |

## Automated tests (no 9router)

Schema, rubric, pipeline with a fake LLM, system detect, RAG, quota, billing, jobs. CI runs them. They do not replace `--live`.

See also: [Pipeline](04-pipeline.md) · [Limits](08-limits.md)

---

[← Operations](06-operations.md) · [Index](README.md) · [Next: Limits →](08-limits.md)
