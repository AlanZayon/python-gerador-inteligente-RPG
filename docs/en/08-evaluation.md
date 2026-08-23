# 8. Evaluation

## 8.1 Two layers

| Layer | Code | Role |
|---|---|---|
| Structural | `validate_campaign` | User jobs: headings, sessions, word floor |
| Heuristic | `evaluate_rubric` | Pipeline + matrix: seven axes, floor 6.0 / overall 7.5 |

Harness: `scripts/eval_reference_campaigns.py` (dry-run fixtures → `reference_matrix.json`; `--live --resume` → `live_matrix.json`). Reference PDFs are **gitignored**. Themes are pinned in the script.

## 8.2 Live matrix (canonical name matching)

Local eval session. Not a literary grade.

| Book | simples | mediana | complexa |
|---|---|---|---|
| Blood & Honor | 8.94 · cons 6.5 | 9.33 · cons 7.0 | 9.35 · cons 7.0 |
| D&D 5e | 9.00 · cons 6.0 | 9.09 · cons 6.5 | 9.32 · cons 7.0 |
| GURPS | 9.39 · cons 7.0 | 9.39 · cons 7.0 | 9.29 · cons 7.0 |
| Fragged | 9.31 · cons 6.5 | 9.21 · cons 6.0 | 9.40 · cons 7.0 |

Mean overall ~**9.25**. Worst cell 8.94. All `passed=true` on this rubric. Weakest axis: **consistency** at the floor.

Before canonical matching, 6/12 failed consistency only (e.g. Blood & Honor simples 4.5) while names were already in the prose.

> **Evidence — matrix / terminal**  
> Expected path: `docs/evidence/eval-matrix.png`

> **Evidence — one cell report**  
> Expected path: `docs/evidence/rubric-report.md`

## 8.3 Automated tests

Schema, rubric, pipeline with a fake LLM, system detect, RAG, quota, billing, jobs. CI runs them. They do not replace `--live`.

## 8.4 Portfolio wording

Say: *four systems, twelve live generations, overall ≥ 8.9 on the internal rubric, consistency at the floor.*  
Do not say: *publication-ready modules* or *any TTRPG PDF*.
