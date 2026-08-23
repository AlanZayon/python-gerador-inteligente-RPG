# Evidence drop zone / Zona de evidências

Chapters in `docs/pt` and `docs/en` already name these files. Missing images do not break the docs; captions tell you what to add.

Do not commit copyrighted PDFs or full campaign manuscripts. Crop screenshots. Use **original** generator excerpts (20–40 lines).

## Files referenced by the docs

| File | Capture |
|---|---|
| `ui-upload.png` | Harness: PDF, complexity, language, theme |
| `ui-progress.png` | Polling / stage message |
| `ui-result.png` | Finished Markdown preview |
| `architecture-runtime.png` | Optional PNG of the architecture |
| `job-status-json.png` | `GET /job-status/:id` (queued and completed) |
| `redis-queues.png` | `rpg:priority_jobs`, `rpg:pending_jobs`, `rpg:processing_jobs`, `rpg:job:*` |
| `faiss-index.png` | `data/indexes/bk_*/` |
| `plan-json-excerpt.md` | Sanitized plan JSON (no book quotes) |
| `session-excerpt.md` | One session: objectives, two approaches, failure |
| `rubric-report.md` | Rubric scores for one cell |
| `eval-matrix.png` | 4×3 live matrix (terminal or sheet) |
| `worker-log.png` | worker.py dequeue → complete |
| `9router-dashboard.png` | Local 9router (no keys) |
| `ci-green.png` | GitHub Actions green |

Once the file exists, replace the italic “expected path” line in a chapter with:

```markdown
![alt](../evidence/ui-upload.png)
```
