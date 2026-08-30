# 3. RAG — retrieval from the book

[← Job](02-job.md) · [Index](README.md) · [Next: Pipeline →](04-pipeline.md)

---

RAG does **not write** the campaign. It builds a **book context** (excerpts + key terms) that the planner and writers must follow. No usable chunks → the job fails with an explicit message.

## Book identity

1. File **SHA-256** → `book_id = bk_{16 hex}`.
2. Perceptual hashes (aHash, dHash, pHash, wHash) on up to six pages. Hamming ≤ `RAG_HAMMING_THRESHOLD` (default 10) and page count within 15% → **reuse** the index (re-exported PDFs).

On disk: `RAG_INDEX_DIR/{book_id}/`.

> **Evidence (optional):** `docs/evidence/faiss-index.png`

## Extraction and chunks

Native text via PyMuPDF → `clean_text` → paragraphs packed to **500–800** MiniLM tokens, **100** overlap. Embedding model: `paraphrase-multilingual-MiniLM-L12-v2` (PT/EN). Runs on CPU.

## Four lanes

| Lane | Query |
|---|---|
| `setting` | Tone, geography, culture + 2 opening chunks |
| `mechanics` | **Preset-specific** (3d6 GURPS, honor/clan, Fragged resources, 5e spells, …) or generic |
| `lore` | Places, factions, creatures + theme |
| `theme` | User theme / hook |

Default `RAG_TOP_K=8` per lane. No LLM classifier.

## Packing

Jaccard 0.7 dedup; at least one chunk per non-empty lane; fill to **floor** then **ceiling**.

| Complexity | Floor | Ceiling |
|---|---|---|
| simples | 2,500 | 4,000 |
| mediana | 4,000 | 6,500 |
| complexa | 5,500 | 9,000 |

Second pass `top_k=16` if still under floor. Output: `book_context`, `key_terms`, `chunks_used`, `token_count`, `lanes_used`.

Each session may retrieve three extra chunks from title/objectives.

### Observed behaviour

On `simples`, packing may use a few large chunks and hit the ceiling early. That is **budget**, not failure. For an unknown book the risk is thin **mechanics** coverage, not zero text.

## System detection

If the request uses `generic`, the worker runs `detect_system_heuristic` on packed context. On a hit, it **re-packs** with the correct mechanics query.

## Dev routes `/rag`

`POST /rag/index`, `POST /rag/generate-campaign`, `GET /rag/books/<id>` — local convenience, **not** the product auth model. Do not expose open in production.

## Non-goals

No LLM page classifier. Lowercase setting names are under-detected. Retrieval cannot prove PDF-faithful lore.

See also: [Pipeline](04-pipeline.md) · [Limits](08-limits.md)

---

[← Job](02-job.md) · [Index](README.md) · [Next: Pipeline →](04-pipeline.md)
