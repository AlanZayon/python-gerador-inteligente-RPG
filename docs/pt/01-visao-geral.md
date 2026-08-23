# 1. Visão geral

## 1.1 O que este sistema faz

Recebe um **PDF de regras de RPG de mesa**, indexa o texto, recupera trechos relevantes, **planeja** uma campanha em JSON, **escreve** o manuscrito em Markdown (visão geral, sessões, apêndice), **pontua** o resultado e **reescreve só as seções fracas**. O utilizador (ou o harness Vue) faz poll até o job terminar e descarrega o Markdown (e, no plano Pro, PDF).

Não copia aventuras publicadas. O livro é **sistema de referência**: procedimentos, tom, vocabulário. O enredo é inventado para obedecer a essas regras.

## 1.2 O que não é

| Não é | Porque |
|---|---|
| Um motor de regras que simula combate | O LLM descreve encontros; não há VTT nem dados reais |
| Um OCR de livros scaneados | Extração é texto embutido no PDF (PyMuPDF). Scan ruim falha cedo |
| Um produto “qualquer livro, qualidade publicada” | A prova empírica são **4 livros × 3 complexidades** |
| O frontend | Vue existe para **evidência visual** do fluxo HTTP |

## 1.3 Peças e fronteiras

```
[Harness Vue]          evidência apenas
        │  JWT / multipart
        ▼
[Flask app.py]         auth, quota, upload S3, enqueue
        │  Redis
        ▼
[worker.py]            BRPOPLPUSH, ack, refund em falha
        │
        ▼
[tasks/campaign_tasks.py]
   PDF → fingerprint/FAISS → pack → plan/write/revise → validate → S3
        │
        ├── 9router (OpenAI-compatible /v1/chat/completions)
        ├── FAISS + MiniLM local
        └── PostgreSQL (users, jobs, billing) + Redis (status TTL)
```

## 1.4 Complexidade (grafo, não só tamanho)

Definido em `services/campaign_schema.py` → `COMPLEXITY_SPEC`:

| Id | Sessões | NPCs | Facções | Locais | Frentes | Mistérios | Finais | Alvo de palavras (plano) | Mínimo estrutural (`campaign_quality`) |
|---|---|---|---|---|---|---|---|---|---|
| `simples` | 1–2 | 4 | 2 | 3 | 1 | 0 | 2 | 1 200 | ≥ 800 palavras |
| `mediana` | 3–4 | 6 | 3 | 5 | 2 | 1 | 3 | 2 800 | ≥ 2 000 |
| `complexa` | 5–7 | 9 | 4 | 7 | 3 | 2 | 4 | 5 200 | ≥ 4 000 |

O validador estrutural (`validate_campaign`) é **hard gate** do job de utilizador. A rubrica heurística (`evaluate_rubric`) guia revisão seletiva e a matriz de eval.

## 1.5 Presets de sistema

`services/system_presets.py` + deteção em `services/system_detect.py`:

`generic` · `dnd5e` · `pf2e` · `coc` · `gurps` · `blood_honor` · `fragged`

Se o cliente manda `generic`, o worker tenta heurística no contexto packed e **re-pack** com a query de mecânica certa.

**Prova de geração ao vivo (local, não commitada):** Blood & Honor, D&D 5e 2024, GURPS Lite 4e, Fragged Empire — três complexidades cada.

## 1.6 Qualidade declarada (o que podes afirmar)

- Jobs assíncronos com progresso, créditos e fallback se o plano JSON falhar.
- Campanhas **estruturalmente** completas nos quatro livros de referência, overall da rubrica ~8,9–9,4 **depois** do matching canónico de nomes.
- A rubrica **satura** em narrativa/gameplay/NPCs; consistência é o eixo frágil (piso 6,0).

> **Evidência — harness: upload**  
> Caminho esperado: `docs/evidence/ui-upload.png`

> **Evidência — harness: resultado**  
> Caminho esperado: `docs/evidence/ui-result.png`
