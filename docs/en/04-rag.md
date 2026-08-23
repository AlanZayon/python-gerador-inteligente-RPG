# 4. RAG

RAG does **not** write the campaign. It builds a **book context** (excerpts + key terms) the planner and writers must follow. Empty retrieval fails the job.

## 4.1 Book identity

1. File **SHA-256** → `book_id = bk_{16 hex}`.
2. Perceptual hashes (aHash, dHash, pHash, wHash) on up to six sampled pages. Hamming ≤ `RAG_HAMMING_THRESHOLD` (default 10) and page count within 15% → **reuse** the index (re-exported PDFs).

On disk: `RAG_INDEX_DIR/{book_id}/`.

> **Evidence — FAISS directory**  
> Expected path: `docs/evidence/faiss-index.png`

## 4.2 Chunking

Native text via PyMuPDF → `clean_text` → paragraphs packed to **500–800** MiniLM tokens, **100** overlap. Embedding model: `paraphrase-multilingual-MiniLM-L12-v2`.

## 4.3 Four lanes

| Lane | Query |
|---|---|
| `setting` | tone, geography, culture + 2 opening chunks |
| `mechanics` | **preset-specific** (3d6 GURPS, honor/clan, Fragged resources, 5e spells, …) or generic |
| `lore` | places, factions, creatures + theme |
| `theme` | user theme/hook |

Default `RAG_TOP_K=8` per lane. No LLM classifier.

## 4.4 Packing

Jaccard 0.7 dedup; at least one chunk per non-empty lane; fill to **floor** then **ceiling**.

| Complexity | Floor | Ceiling |
|---|---|---|
| simples | 2,500 | 4,000 |
| mediana | 4,000 | 6,500 |
| complexa | 5,500 | 9,000 |

Second pass `top_k=16` if still under floor. Output: `book_context`, `key_terms`, `chunks_used`, `token_count`, `lanes_used`.

Live `simples` runs often packed ~5 large chunks (ceiling), which is budget behaviour. For an unknown book the risk is **thin mechanics coverage**, not zero text.

Each session may `retrieve` three extra chunks from title/objectives.

## 4.5 Dev routes `/rag`

Unauthenticated convenience (`POST /rag/index`, `POST /rag/generate-campaign`, `GET /rag/books/<id>`). **Not** the product path. Do not expose open in production.

## 4.6 Non-goals

No LLM page classifier. Lowercase setting names are under-detected. Retrieval cannot *prove* PDF-faithful lore.
