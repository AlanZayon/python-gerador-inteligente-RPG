# 4. RAG — recuperação a partir do livro

O RAG **não** gera a campanha. Ele monta um **contexto de livro** (excertos + termos) que o planejador e os escritores são obrigados a respeitar. Sem chunks úteis, o job falha com mensagem explícita.

## 4.1 Identidade do livro

`services/rag/fingerprint.py` + `ensure_indexed`:

1. **SHA-256** do ficheiro → `book_id = bk_{16 hex}`. Mesmo bytes = mesmo índice.
2. Hashes percetuais (aHash, dHash, pHash, wHash) de até 6 páginas amostradas. Hamming ≤ `RAG_HAMMING_THRESHOLD` (default 10) e contagem de páginas dentro de 15% → **reutiliza** índice mesmo se o PDF foi reexportado.

Índice em `RAG_INDEX_DIR/{book_id}/`: FAISS, `chunks.json`, metadados.

> **Evidência — pasta FAISS**  
> Caminho esperado: `docs/evidence/faiss-index.png`

## 4.2 Extração e chunks

1. PyMuPDF (`extract_pdf_text`) — texto nativo, não OCR.
2. Limpeza (`clean_text`).
3. `chunk_text`: parágrafos agregados até **500–800** tokens (tokenizer do MiniLM), overlap **100** tokens.

Modelo: `paraphrase-multilingual-MiniLM-L12-v2` (PT/EN no mesmo espaço). CPU. Warning conhecido: documentos enormes no tokenizer (>128) na fase de indexação — o encode por chunk é que importa.

## 4.3 Quatro lanes

`services/rag/retrieval.py` → `retrieve_coverage`:

| Lane | Query |
|---|---|
| `setting` | tom, geografia, cultura + 2 chunks de abertura do livro |
| `mechanics` | query **por preset** (3d6 GURPS, honra/clã Blood & Honor, recursos Fragged, magias 5e, …); senão genérica |
| `lore` | locais, facções, criaturas + tema |
| `theme` | tema/hook do utilizador |

Default `RAG_TOP_K=8` por lane. Sem classificador LLM.

## 4.4 Packing (`pack_campaign_context`)

`services/rag/context_packer.py`:

1. Dedup Jaccard 0,7 dentro da lane e entre lanes.
2. Pelo menos um chunk por lane não vazia.
3. Enche até ao **chão** de tokens; depois até ao **teto**.

| Complexidade | Chão | Teto |
|---|---|---|
| simples | 2 500 | 4 000 |
| mediana | 4 000 | 6 500 |
| complexa | 5 500 | 9 000 |

Se ainda estiver abaixo do chão, segunda passagem com `top_k=16`.

Saída: `book_context` (Markdown por lane), `key_terms` (próprios capitalizados, stopwords PT/EN filtradas), `chunks_used`, `token_count`, `lanes_used`.

**Observação empírica:** no `simples` ao vivo o packer usou ~5 chunks (teto atingido com chunks grandes). Isso é orçamento, não “falha de RAG”. Para livro desconhecido, o risco é **má cobertura de mecânica**, não ausência total de texto.

Durante cada sessão, `retrieve_fn` busca mais 3 chunks com o título/objetivos da sessão.

## 4.5 Endpoints `/rag` (dev)

Blueprint **sem auth** (`routes/rag.py`): `POST /rag/index`, `POST /rag/generate-campaign`, `GET /rag/books/<id>`. Conveniência local — **não** é o caminho de produto (esse é o worker). Não expor aberto em produção sem proteção.

## 4.6 O que o RAG não faz

- Não classifica páginas com LLM.
- Não garante que um termo raro em caixa-baixa entre em `key_terms`.
- Não prova que a campanha está correta contra o PDF; só aumenta a probabilidade de o modelo ver os procedimentos certos.
