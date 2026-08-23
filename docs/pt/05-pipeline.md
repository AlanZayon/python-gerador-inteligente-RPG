# 5. Pipeline de qualidade (plan → write → revise)

Implementação: `services/campaign_pipeline.py` → `generate_campaign_markdown`. Chamado por `tasks/campaign_tasks.py` depois do pack.

## 5.1 Por que não multi-agente

| Desenho | Qualidade longa | Custo | Teste |
|---|---|---|---|
| Um prompt | Fraca | Mínimo | Fácil |
| Outline → expand (legado) | Média; expand reinventava o mundo | Médio | Médio |
| **Plano JSON → escrita incremental → rubrica → splice** | Nomes e ramos estáveis | +1 plano + N sessões + apêndice + ≤2 revisões | Fakes de LLM nos testes |
| Crew de agentes | Marginal | Alto | Difícil |

O crítico é **código**: `evaluate_rubric` + rewrite da secção mais fraca. Não um segundo “agente revisor” livre.

## 5.2 Campaign State

O plano é o único sítio onde **nascem nomes**. `PLAN_JSON_INSTRUCTIONS` pede título, premissa, questão temática, conflito, stakes, temas, `grounded_terms`, `rules_to_use`, facções, NPCs (want/secret/tie/quirk), locais, frentes (impulse/portents/doom), mistérios + pistas, sessões (cenas com ≥2 abordagens, escolhas if_a/if_b), finais, segredos do mestre.

`normalize_plan`:

- Rejeita título curto / premissa &lt; 40 caracteres / sessões a menos.
- Aceita NPC/facção/local como string ou objeto.
- Aceita escolhas como string ou `{decision, if_a, if_b}`.
- Completa escolhas em falta a partir das abordagens da cena.
- Completa abordagens até 2 (`negotiate` / `investigate quietly` / `force a confrontation`).
- **Canónico:** `Isamu (The Daimyo)` → nome `Isamu`, cargo no `role`.

`plan_is_structurally_complete` compara com `COMPLEXITY_SPEC`. `_plan_from_llm` tenta 2 vezes (a segunda lista as falhas). O pipeline ainda pode **usar** um plano incompleto se o JSON for válido — melhor que cair no fallback.

Fallback: `pipeline = fallback-full` e o prompt único antigo (`build_campaign_prompt`). O job não morre por JSON mau.

> **Evidência — excerto do plano**  
> Caminho esperado: `docs/evidence/plan-json-excerpt.md`

## 5.3 Escrita

1. **Overview + hook** — só nomes do digest.
2. **Cada sessão** — brief JSON + digest + resumo das 3 sessões anteriores + retrieve extra.
3. **Apêndice** — NPCs, inimigos, desafios, finais, mapas, recompensas.

Labels de secção passam por `campaign_i18n` (PT/EN).

`state_digest` (~4500 chars) é a bíblia injetada em todos os prompts de escrita.

> **Evidência — uma sessão gerada**  
> Caminho esperado: `docs/evidence/session-excerpt.md`

## 5.4 Rubrica heurística

`services/campaign_eval.py`. Categorias 0–10, média **ponderada**:

| Categoria | Peso | Sinais (resumo) |
|---|---|---|
| narrative | 1,2 | stake/conflict/theme, nº sessões, clocks/fronts, headings |
| gameplay | 1,2 | “if the players”, stealth/social, falha |
| npcs | 1,0 | `###` headings, want/secret/role, contagem no estado |
| world | 1,0 | facções/locais/frentes no estado + termos no texto |
| content | 0,8 | rácio palavras/alvo, penalidade tropes genéricos, reuso de nomes |
| consistency | 1,3 | nomes do estado presentes no Markdown (nome canónico / 1.º token ≥4) |
| gm_utility | 1,1 | DC/3d6/check, GM notes, clues/rewards |

**Pass:** overall ≥ **7,5** e todas ≥ **6,0**.

Consistência **não** é análise literária. É “o plano e o manuscrito falam das mesmas entidades”. Títulos entre parênteses no JSON partiam o score (4,5 com a história coerente). O matching canónico corrige isso.

A rubrica **satura** em narrative/gameplay/npcs nos runs ao vivo — útil como piso, fraca como ranking fino.

## 5.5 Revisão seletiva

Até `MAX_REVISION_PASSES = 2` enquanto `passed` é falso. Escolhe um H2 (overview, NPCs, ou sessão 1 se gameplay fraco), `build_revise_prompt`, substitui só aquele bloco (`_splice_section`).

## 5.6 Hard gate estrutural (job)

Depois do pipeline, `validate_campaign` ainda exige mínimo de palavras, `## Overview` / `## Sessão N`, `## NPCs`, e (se houver fichas) nomes dos PCs. Score 0–100 no job ≠ overall da rubrica ×10, embora `rubric_as_100` vá nos metadados.

`normalize_campaign_markdown` e `heal_missing_sections` tentam reparar headings antes do upload.

## 5.7 Chamadas LLM típicas (caminho feliz)

`2` tentativas de plano + `1` overview + `N` sessões + `1` apêndice + `0–2` revisões.

Timeout default 600s, retries 3, `max_tokens` 8192, modelo por complexidade (`LLM_MODEL_LITE|FLASH|PRO`, default `my-combo` via 9router).
