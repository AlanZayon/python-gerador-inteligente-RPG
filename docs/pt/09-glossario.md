# 9. Glossário

[← Limites](08-limites.md) · [Índice](README.md)

---

| Termo | Significado neste repositório |
|---|---|
| **Job** | Unidade assíncrona: PDF + parâmetros → um Markdown |
| **Campaign State / plano** | JSON canónico da campanha; fonte dos nomes |
| **Digest** | Render textual truncado do estado, injetado nos prompts de escrita |
| **Lane** | Uma de quatro queries de retrieval (setting, mechanics, lore, theme) |
| **Packing** | Seleção de chunks sob orçamento de tokens |
| **Preset** | Id de sistema (`gurps`, `dnd5e`, …) que muda query de mecânica e bloco de prompt |
| **Rubrica** | Score heurístico 0–10 em 7 categorias |
| **Hard gate** | `validate_campaign`: se falhar, o job do utilizador não completa com qualidade aceitável |
| **9router** | Gateway local OpenAI-compatible (`NINEROUTER_URL`) |
| **book_id** | `bk_` + 16 hex do SHA-256 (ou índice reutilizado por Hamming) |
| **simples / mediana / complexa** | Tamanho do **grafo** da campanha, não um adjetivo de qualidade |
| **Front** | Pressão off-screen (impulse, portents, doom) |
| **Fallback-full** | Um único prompt clássico quando o plano JSON não serve |
| **Ack** | `LREM` do job em `rpg:processing_jobs` após sucesso ou falha terminal |

---

[← Limites](08-limites.md) · [Índice](README.md)
