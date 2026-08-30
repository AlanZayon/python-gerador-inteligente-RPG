# 7. Avaliação

[← Operação](06-operacao.md) · [Índice](README.md) · [Seguinte: Limites →](08-limites.md)

---

Há duas camadas de qualidade. Não as misture.

| Camada | Código | Papel |
|---|---|---|
| Estrutural | `validate_campaign` | Job do utilizador: headings, sessões, palavras |
| Heurística | `evaluate_rubric` | Pipeline + matriz: 7 eixos, piso 6,0 / overall 7,5 |

## Script de matriz

`scripts/eval_reference_campaigns.py`

| Modo | Saída |
|---|---|
| Dry-run (sem LLM) | `examples/eval_runs/reference_matrix.json` (fixtures) |
| `--live --resume` | Markdown local + `live_matrix.json` |

Livros de referência (gitignored na raiz do repo): Blood & Honor, PHB 5e 2024, GURPS Lite 4e, Fragged Empire. Temas fixos no script para a matriz ser comparável.

```bash
.\venv\Scripts\python.exe scripts\eval_reference_campaigns.py --live --resume
```

## Matriz ao vivo (nomes canónicos)

Valores da sessão de eval local. **Não** são nota literária.

| Livro | simples | mediana | complexa |
|---|---|---|---|
| Blood & Honor | 8,94 · cons 6,5 | 9,33 · cons 7,0 | 9,35 · cons 7,0 |
| D&D 5e | 9,00 · cons 6,0 | 9,09 · cons 6,5 | 9,32 · cons 7,0 |
| GURPS | 9,39 · cons 7,0 | 9,39 · cons 7,0 | 9,29 · cons 7,0 |
| Fragged | 9,31 · cons 6,5 | 9,21 · cons 6,0 | 9,40 · cons 7,0 |

- Média overall ~**9,25**; pior célula **8,94**.
- Todas `passed=true` neste critério.
- Eixo mais fraco: **consistency** no piso (6,0–7,0).

Antes do matching canónico, 6/12 falhavam só em consistency (ex. Blood & Honor simples 4,5) com os NPCs já presentes no texto (`Isamu` vs `Isamu (The Daimyo)` no plano).

> **Evidência (opcional):** `docs/evidence/eval-matrix.png` · `docs/evidence/rubric-report.md`

## O que a métrica prova e o que não prova

| Prova | Não prova |
|---|---|
| Estrutura jogável (sessões, NPCs, escolhas sinalizadas) | Correção de regras face ao PDF |
| Reuso dos nomes do plano | Qualidade literária / mesa real |
| Ausência grosseira de tropes genéricos | Que qualquer livro novo terá o mesmo overall |

## Testes automatizados (sem 9router)

`tests/test_campaign_schema.py`, `test_campaign_eval.py`, `test_campaign_pipeline.py` (LLM fake), `test_system_detect.py`, mais RAG, quota, billing, jobs. A CI corre a suíte. Não substituem `--live`.

Ver também: [Pipeline](04-pipeline.md) · [Limites](08-limites.md)

---

[← Operação](06-operacao.md) · [Índice](README.md) · [Seguinte: Limites →](08-limites.md)
