# 9. Glossary

[← Limits](08-limits.md) · [Index](README.md)

---

| Term | Meaning in this repository |
|---|---|
| **Job** | One async unit: PDF + params → one Markdown |
| **Campaign State / plan** | Canonical JSON; source of names |
| **Digest** | Truncated textual render of state for writer prompts |
| **Lane** | One of four retrieval queries |
| **Packing** | Chunk selection under a token budget |
| **Preset** | System id that switches mechanics query + prompt block |
| **Rubric** | Heuristic 0–10 scores in seven categories |
| **Hard gate** | `validate_campaign` for user-facing success |
| **9router** | Local OpenAI-compatible gateway |
| **book_id** | `bk_` + 16 hex of SHA-256 (or Hamming reuse) |
| **simples / mediana / complexa** | Campaign **graph** size, not a quality adjective |
| **Front** | Off-screen pressure (impulse, portents, doom) |
| **Fallback-full** | Legacy single prompt when JSON planning fails |
| **Ack** | `LREM` of the job from `rpg:processing_jobs` after terminal success or failure |

---

[← Limits](08-limits.md) · [Index](README.md)
