# 3. RAG — recuperação a partir do livro

[← Job](02-job.md) · [Índice](README.md) · [Seguinte: Pipeline →](04-pipeline.md)

---

O RAG **não escreve** a campanha. Monta um **contexto de livro** (excertos + termos-chave) que o planejador e os escritores devem seguir. Sem chunks úteis, o job falha com mensagem explícita.

## Identidade do livro

`services/rag/fingerprint.py` + `ensure_indexed`:

1. **SHA-256** do ficheiro → `book_id = bk_{16 hex}`. Mesmos bytes = mesmo índice.
2. Hashes percetuais (aHash, dHash, pHash, wHash) de até 6 páginas. Hamming ≤ `RAG_HAMMING_THRESHOLD` (default 10) e contagem de páginas dentro de 15% → **reutiliza** índice mesmo se o PDF foi reexportado.

Ficheiros em `RAG_INDEX_DIR/{book_id}/`: FAISS, `chunks.json`, metadados.

> **Evidência (opcional):** `docs/evidence/faiss-index.png`

## Extração e chunks

1. PyMuPDF — texto nativo (não OCR).
2. `clean_text`.
3. `chunk_text`: parágrafos até **500–800** tokens (tokenizer MiniLM), overlap **100**.

Modelo de embedding: `paraphrase-multilingual-MiniLM-L12-v2` (PT/EN). Corre em CPU.

## Quatro lanes

`retrieve_coverage` em `services/rag/retrieval.py`:

| Lane | O que pede |
|---|---|
| `setting` | Tom, geografia, cultura + 2 chunks de abertura do livro |
| `mechanics` | Query **por preset** (3d6 GURPS, honra/clã, recursos Fragged, magias 5e, …); senão genérica |
| `lore` | Locais, facções, criaturas + tema |
| `theme` | Tema / hook do pedido |

Default `RAG_TOP_K=8` por lane. Sem classificador LLM.

## Packing

`pack_campaign_context` (`services/rag/context_packer.py`):

1. Dedup Jaccard 0,7 dentro e entre lanes.
2. Pelo menos um chunk por lane não vazia.
3. Enche até ao **chão** de tokens; depois até ao **teto**.

| Complexidade | Chão | Teto |
|---|---|---|
| simples | 2 500 | 4 000 |
| mediana | 4 000 | 6 500 |
| complexa | 5 500 | 9 000 |

Se ainda estiver abaixo do chão → segunda passagem com `top_k=16`.

Saída: `book_context`, `key_terms`, `chunks_used`, `token_count`, `lanes_used`.

Durante cada sessão, o pipeline pode pedir mais 3 chunks com título/objetivos da sessão.

### Comportamento observado

No `simples`, o packer pode usar poucos chunks grandes e atingir o teto cedo. Isso é **orçamento**, não falha. O risco num livro desconhecido é cobertura fraca de **mecânica**, não ausência total de texto.

## Deteção de sistema

Se o pedido vier com `generic`, o worker corre `detect_system_heuristic` no contexto packed. Se acertar (`gurps`, `dnd5e`, …), **re-pack** com a query de mecânica correta.

## Endpoints `/rag` (dev)

`POST /rag/index`, `POST /rag/generate-campaign`, `GET /rag/books/<id>` — conveniência local, **sem** o mesmo modelo de auth do produto. Não expor aberto em produção.

## O que o RAG não faz

- Não classifica páginas com LLM.
- Não garante termos em caixa-baixa em `key_terms`.
- Não prova fidelidade ao PDF; só aumenta a chance de o modelo ver os procedimentos certos.

Ver também: [Pipeline](04-pipeline.md) · [Limites](08-limites.md)

---

[← Job](02-job.md) · [Índice](README.md) · [Seguinte: Pipeline →](04-pipeline.md)
