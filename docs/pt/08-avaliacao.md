# 8. Avaliação

## 8.1 Dois níveis

| Camada | Código | Papel |
|---|---|---|
| Estrutural | `validate_campaign` | Job do utilizador: headings, sessões, palavras |
| Heurística | `evaluate_rubric` | Pipeline + matriz: 7 eixos, piso 6,0 / overall 7,5 |

Script: `scripts/eval_reference_campaigns.py`

- Dry-run: fixtures, escreve `examples/eval_runs/reference_matrix.json`
- `--live --resume`: gera ou reusa Markdown local, escreve `live_matrix.json`

Livros de referência (ficheiros **gitignored** na raiz): Blood & Honor, PHB 5e 2024, GURPS Lite 4e, Fragged Empire. Temas fixos no script para tornar a matriz comparável.

## 8.2 Matriz ao vivo (reavaliação com nomes canónicos)

Valores gravados na sessão de eval local. **Não** são nota literária. Células vazias: cola o print.

| Livro | simples | mediana | complexa |
|---|---|---|---|
| Blood & Honor | 8,94 · cons 6,5 | 9,33 · cons 7,0 | 9,35 · cons 7,0 |
| D&D 5e | 9,00 · cons 6,0 | 9,09 · cons 6,5 | 9,32 · cons 7,0 |
| GURPS | 9,39 · cons 7,0 | 9,39 · cons 7,0 | 9,29 · cons 7,0 |
| Fragged | 9,31 · cons 6,5 | 9,21 · cons 6,0 | 9,40 · cons 7,0 |

Média overall ~**9,25**. Pior célula 8,94. Todas `passed=true` neste critério. Eixo mais fraco: **consistency** no piso.

Antes do matching canónico, 6/12 falhavam só em consistency (ex. Blood & Honor simples 4,5) com NPCs presentes no texto (`Isamu` vs `Isamu (The Daimyo)`).

> **Evidência — matriz / terminal**  
> Caminho esperado: `docs/evidence/eval-matrix.png`

> **Evidência — relatório de uma célula**  
> Caminho esperado: `docs/evidence/rubric-report.md`

## 8.3 Testes automatizados (sem 9router)

`tests/test_campaign_schema.py`, `test_campaign_eval.py`, `test_campaign_pipeline.py` (LLM fake), `test_system_detect.py`, mais RAG, quota, billing, jobs. CI corre a suíte.

Não substituem o `--live`.

## 8.4 Como usar isto no portfólio

Afirmar: *quatro sistemas, doze gerações reais, overall ≥ 8,9 na rubrica interna, consistência no piso.*  
Não afirmar: *módulo pronto a publicar* ou *qualquer PDF de RPG*.
