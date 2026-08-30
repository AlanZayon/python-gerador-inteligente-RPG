# 4. Pipeline de geração

[← RAG](03-rag.md) · [Índice](README.md) · [Seguinte: API →](05-api.md)

---

Implementação: `generate_campaign_markdown` em `services/campaign_pipeline.py`, chamada por `tasks/campaign_tasks.py` depois do pack RAG.

## Ideia central

1. **Planear** a campanha em JSON (Campaign State).
2. **Escrever** o manuscrito por partes (overview → sessões → apêndice).
3. **Pontuar** com rubrica heurística.
4. **Reescrever** só a secção mais fraca (até 2 vezes).
5. Se o plano JSON falhar de vez → **fallback** para o prompt único antigo (o job não morre).

## Por que este desenho (e não multi-agente)

| Abordagem | Continuidade | Custo | Testabilidade |
|---|---|---|---|
| Um prompt só | Fraca em textos longos | Mínimo | Fácil |
| Outline → expand (legado) | Expand reinventava o mundo | Médio | Médio |
| **Plano JSON → escrita → rubrica → splice** | Nomes e ramos estáveis | +1 plano + N sessões + ≤2 revisões | LLM fake nos testes |
| Crew multi-agente | Marginal face ao plano+crítico | Alto | Difícil |

O “crítico” é **código** (`evaluate_rubric` + `_splice_section`), não um segundo LLM livre.

## Campaign State (plano)

O plano é o único sítio onde **nascem nomes**. Campos pedidos: título, premissa, questão temática, conflito, stakes, temas, `grounded_terms`, `rules_to_use`, facções, NPCs (want/secret/tie/quirk), locais, frentes (impulse/portents/doom), mistérios + pistas, sessões (cenas com ≥2 abordagens, escolhas), finais, segredos do mestre.

`normalize_plan` (`services/campaign_schema.py`):

- Rejeita título curto / premissa &lt; 40 caracteres / sessões a menos do mínimo.
- Aceita NPC/facção/local como string ou objeto.
- Aceita escolhas como string ou `{decision, if_a, if_b}`.
- Completa escolhas em falta a partir das abordagens da cena.
- Completa abordagens até 2.
- Canónico: `Isamu (The Daimyo)` → nome `Isamu`, cargo no `role`.

`plan_is_structurally_complete` compara com `COMPLEXITY_SPEC`. `_plan_from_llm` tenta até 2 vezes (a segunda lista as falhas).

> **Evidência (opcional):** `docs/evidence/plan-json-excerpt.md`

## Complexidade = tamanho do grafo

| Id | Sessões | NPCs | Facções | Locais | Frentes | Mistérios | Finais | Alvo palavras (plano) | Mínimo estrutural |
|---|---|---|---|---|---|---|---|---|---|
| simples | 1–2 | 4 | 2 | 3 | 1 | 0 | 2 | 1 200 | ≥ 800 |
| mediana | 3–4 | 6 | 3 | 5 | 2 | 1 | 3 | 2 800 | ≥ 2 000 |
| complexa | 5–7 | 9 | 4 | 7 | 3 | 2 | 4 | 5 200 | ≥ 4 000 |

## Escrita

1. **Overview + hook** — só nomes do digest.
2. **Cada sessão** — brief JSON + digest + resumo das 3 sessões anteriores + retrieve extra.
3. **Apêndice** — NPCs, inimigos, desafios, finais, mapas, recompensas.

`state_digest` (~4 500 chars) é a bíblia injetada em todos os prompts de escrita. Labels de secção via `campaign_i18n` (PT/EN).

> **Evidência (opcional):** `docs/evidence/session-excerpt.md`

## Rubrica heurística

`services/campaign_eval.py`. Categorias 0–10, média ponderada:

| Categoria | Peso | Sinais |
|---|---|---|
| narrative | 1,2 | stake/conflict/theme, sessões, clocks/fronts |
| gameplay | 1,2 | “if the players”, stealth/social, falha |
| npcs | 1,0 | headings `###`, want/secret/role |
| world | 1,0 | facções/locais/frentes + termos no texto |
| content | 0,8 | rácio palavras/alvo, anti-tropes genéricos |
| consistency | 1,3 | nomes do estado no Markdown (nome canónico / 1.º token) |
| gm_utility | 1,1 | DC/3d6/check, GM notes, clues |

**Pass:** overall ≥ **7,5** e todas ≥ **6,0**.

Consistência = overlap de entidades plano↔manuscrito, **não** análise literária. Títulos entre parênteses no JSON (`Isamu (The Daimyo)` vs `Isamu` no texto) partiam o score; o matching canónico corrige isso.

A rubrica **satura** em narrative/gameplay/npcs nos runs ao vivo: útil como piso, fraca como ranking fino entre duas campanhas boas.

## Revisão seletiva

Enquanto `passed` for falso e `passes < 2`: escolhe um H2 (overview, NPCs, ou sessão 1 se gameplay fraco), `build_revise_prompt`, substitui só aquele bloco.

## Hard gate estrutural (job do utilizador)

Depois do pipeline, `validate_campaign` exige mínimo de palavras, `## Overview`, sessões numeradas, `## NPCs` (e nomes dos PCs se houver fichas). O `quality_score` 0–100 do job é **estrutural**; o overall da rubrica vive nos metadados (`rubric` / `rubric_as_100`).

`normalize_campaign_markdown` e `heal_missing_sections` tentam reparar headings antes do upload.

## Chamadas LLM (caminho feliz)

Até 2 tentativas de plano + 1 overview + N sessões + 1 apêndice + 0–2 revisões.

Timeout default 600s, 3 retries, `max_tokens` 8192. Modelo por complexidade: `LLM_MODEL_LITE` / `FLASH` / `PRO` (default `my-combo` via 9router).

Ver também: [Avaliação](07-avaliacao.md) · [RAG](03-rag.md) · [Limites](08-limites.md)

---

[← RAG](03-rag.md) · [Índice](README.md) · [Seguinte: API →](05-api.md)
