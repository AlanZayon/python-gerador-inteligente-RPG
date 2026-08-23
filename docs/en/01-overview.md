# 1. Overview

## 1.1 What the system does

It accepts a **tabletop RPG rulebook PDF**, indexes the text, retrieves relevant passages, **plans** a campaign as JSON, **writes** Markdown (overview, sessions, appendix), **scores** the draft, and **rewrites only weak sections**. A client (or the Vue harness) polls the job and downloads Markdown (Pro: PDF export).

It does not pirate published adventures. The book is a **rules and tone reference**. Plot is original.

## 1.2 What it is not

| Not | Why |
|---|---|
| A combat simulator / VTT | The LLM describes scenes; nothing rolls dice |
| OCR for scanned books | Extraction is native PDF text (PyMuPDF) |
| “Any book, published-module quality” | Live proof is **4 books × 3 complexities** |
| The frontend | Vue exists to **show** the HTTP flow |

## 1.3 Moving parts

```
[Vue harness]            evidence only
        │  JWT / multipart
        ▼
[Flask app.py]           auth, quota, S3 upload, enqueue
        │  Redis
        ▼
[worker.py]              BRPOPLPUSH, ack, refund on failure
        ▼
[tasks/campaign_tasks.py]
   PDF → fingerprint/FAISS → pack → plan/write/revise → validate → S3
        ├── 9router (OpenAI-compatible chat completions)
        ├── local FAISS + MiniLM
        └── PostgreSQL + Redis job hashes
```

## 1.4 Complexity is graph size

From `COMPLEXITY_SPEC` in `services/campaign_schema.py`:

| Id | Sessions | NPCs | Factions | Locations | Fronts | Mysteries | Endings | Plan word target | Structural floor |
|---|---|---|---|---|---|---|---|---|---|
| `simples` | 1–2 | 4 | 2 | 3 | 1 | 0 | 2 | 1,200 | ≥ 800 words |
| `mediana` | 3–4 | 6 | 3 | 5 | 2 | 1 | 3 | 2,800 | ≥ 2,000 |
| `complexa` | 5–7 | 9 | 4 | 7 | 3 | 2 | 4 | 5,200 | ≥ 4,000 |

`validate_campaign` is the **user-job hard gate**. `evaluate_rubric` drives selective revision and the eval matrix.

## 1.5 System presets

`generic`, `dnd5e`, `pf2e`, `coc`, `gurps`, `blood_honor`, `fragged`.

If the client sends `generic`, the worker may heuristically detect the system from packed text and **re-pack** with the right mechanics query.

**Live local eval (not committed):** Blood & Honor, D&D 5e 2024, GURPS Lite 4e, Fragged Empire × three complexities.

## 1.6 What you can honestly claim

- Async jobs with progress, credits, and a full-prompt fallback if JSON planning fails.
- Structurally complete campaigns on four reference books; rubric overall ~8.9–9.4 **after** canonical name matching.
- The rubric **saturates** on narrative/gameplay/NPCs; consistency is the weak axis (floor 6.0).

> **Evidence — harness upload**  
> Expected path: `docs/evidence/ui-upload.png`

> **Evidence — harness result**  
> Expected path: `docs/evidence/ui-result.png`
