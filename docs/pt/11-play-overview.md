# 11. Play — visão geral

[← Voz](10-voz.md) · [Índice](README.md) · [Seguinte: GM Runtime →](12-gm-runtime.md)

---

Geração termina num **Job** (manuscrito Markdown + plano). Play começa só quando o anfitrião cria explicitamente uma **Campaign** a partir desse Job ([ADR 0001](../adr/0001-campaign-separate-from-job.md)).

## Job ≠ Campaign

| Conceito | Papel |
|---|---|
| **Job** | História de geração: PDF, créditos/legado, chaves S3, status assíncrono, Blueprint persistido |
| **Campaign** | Instância jogável: cópia do Blueprint, roster de Characters, membership, Campaign State |

Rejeitámos sobrecarregar o Job como agregado de mesa: mistura metadados de geração com runtime.

## Blueprint vs Campaign State

| Termo | Significado |
|---|---|
| **Campaign Blueprint** | Desenho durável (facções, NPCs, locais, frentes, mistérios, sessões de manuscrito, segredos, finais). Copiado para a Campaign na criação. |
| **Campaign State** | Verdade mutável em play: cena atual, flags de NPC, progresso, inventário/HP se rastreado, Roll Call pendente, Combat Encounter ativo. |

O Blueprint é canónico para o desenho; o Markdown é apresentação derivada. Em play, o runtime não re-parseia a prosa para descobrir a verdade do mundo ([ADR 0002](../adr/0002-blueprint-vs-campaign-state.md)).

> Nos capítulos de geração, “Campaign State / plano” ainda pode aparecer como nome legado do JSON do planner. Em Play, use **Blueprint** para o plano e **Campaign State** só para o runtime.

## Peças à mesa

| Peça | Definição |
|---|---|
| **GameSession** | Sala multiplayer ao vivo (lobby → active → ended), com convite e presença |
| **Player** | Assento na Campaign / GameSession: um User na mesa, opcionalmente ligado a um Character |
| **Character** | PC no roster (vindos das fichas da geração). O Player **reclama** um Character no lobby |
| **User** | Conta Clerk; pode ter vários assentos Player em Campaigns diferentes |
| **NPC** | Definido no Blueprint e/ou mutado no Campaign State — não é Character |

## Fluxo mental

```text
Job completed
    → host cria Campaign (copia Blueprint + knowledge handles)
    → Players entram na GameSession / lobby
    → cada Player reclama um Character
    → sessão active → Game Master Runtime narra e muta Campaign State
```

## Onde está no código

| Área | Pasta / ficheiros |
|---|---|
| Campaigns | `services/play/campaigns.py`, `routes/campaigns.py` |
| Sessions | `services/play/sessions.py`, `routes/sessions.py` |
| WebSocket | `routes/ws_sessions.py`, `services/play/hub.py`, `services/play/sync.py` |
| GM | `services/play/gm/` |

Ver também: [GM Runtime](12-gm-runtime.md) · [Realtime](15-realtime.md)

---

[← Voz](10-voz.md) · [Índice](README.md) · [Seguinte: GM Runtime →](12-gm-runtime.md)
