# 12. Game Master Runtime

[← Play](11-play-overview.md) · [Índice](README.md) · [Seguinte: Roll Call →](13-roll-call.md)

---

O **Game Master Runtime** é o loop da aplicação que transforma intenção do jogador + Blueprint + Campaign State + memória + retrieval de regras em decisões do mestre, chamadas a **GM Tools**, narração e atualizações de estado.

Não é um chatbot: o modelo sugere e narra; as ferramentas do servidor são a fonte de verdade para dados, HP e mutações.

## Entradas e saídas

```text
Player action (texto / voz STT)
    → contexto: Blueprint digest, Campaign State, memórias permitidas, pack RAG
    → LLM (9router) + tool calls
    → GM Tools executam no servidor
    → Campaign State / eventos gravados
    → narração pública (+ opcional Voice Direction → TTS)
```

## GM Tools (autoridade)

Especificações em `services/play/gm/tools.py`. Exemplos:

| Tool | Função |
|---|---|
| `lookup_rules` | Pesquisa o BookIndex antes de um check de PC |
| `request_roll` | Emite Roll Call (não rola) — ver [Roll Call](13-roll-call.md) |
| `roll_dice` / `perform_check` | Só para rolagens ocultas GM/NPC |
| `read_world_state` / `update_world_state` | Lê / faz patch do Campaign State |
| `create_event` | Anexa um evento de jogo |
| tools de combate | `begin_combat`, `apply_harm`, `next_turn`, … — ver [Combat](14-combat.md) |

Resultados das tools são autoritativos. O modelo **não** inventa totais de dados ou HP quando existe tool.

## Memória privada por Character

Verdades do mundo podem ser conhecidas só por um Character (ou subconjunto). O GM (servidor) pode conhecer tudo; cada jogador só recebe o que o Character dele pode saber. Evite tratar memória pública/partilhada como default.

## Voz depois do estado

A camada de voz (Narration → Voice Director → TTS) corre **depois** do Campaign State estar gravado. Voice Direction (Audio Tags como `[whispers]`) nunca altera regras, inventário, combate ou quests. Detalhe operacional: [Voz](10-voz.md).

## Onde está no código

| Peça | Local |
|---|---|
| Runtime / ações | `services/play/gm/runtime.py`, `actions.py` |
| LLM live / mock | `live_llm.py`, `mock_llm.py` |
| Estado | `state.py` |
| RAG em play | `rag_context.py` |
| Tools | `tools.py` |

---

[← Play](11-play-overview.md) · [Índice](README.md) · [Seguinte: Roll Call →](13-roll-call.md)
