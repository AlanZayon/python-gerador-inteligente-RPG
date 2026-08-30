# Evidence files (optional)

Drop diagrams, logs, and short excerpts **here**. Chapters in `docs/pt` and `docs/en` already name these files. Missing files do not break the docs.

Do not commit copyrighted PDFs or full campaign manuscripts. Prefer cropped screenshots and short original excerpts (20–40 lines).

| File | What to capture |
|---|---|
| `architecture-runtime.png` | Optional PNG of the architecture (Mermaid is already in the docs) |
| `job-status-json.png` | `GET /job-status/:id` (queued and completed) |
| `redis-queues.png` | Keys `rpg:priority_jobs`, `rpg:pending_jobs`, `rpg:processing_jobs`, `rpg:job:*` |
| `faiss-index.png` | Folder `data/indexes/bk_*` |
| `plan-json-excerpt.md` | Sanitized campaign plan JSON (no book quotes) |
| `session-excerpt.md` | One generated session: objectives, two approaches, failure |
| `rubric-report.md` | Rubric scores for one matrix cell |
| `eval-matrix.png` | 4×3 live matrix (terminal or sheet) |
| `worker-log.png` | `worker.py` dequeue → complete |
| `9router-dashboard.png` | Local 9router health / models (no API keys) |
| `ci-green.png` | GitHub Actions Backend CI green |

Once a file exists, replace the italic “evidence” line in a chapter with:

```markdown
![description](../evidence/job-status-json.png)
```
