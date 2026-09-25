# 14. Combat tracker

[← Roll Call](13-roll-call.md) · [Índice](README.md) · [Seguinte: Realtime →](15-realtime.md)

---

Combate à mesa é um **tracker leve** no Campaign State — não um motor multi-sistema compilado ([ADR 0008](../adr/0008-light-combat-tracker.md)).

Procedimentos (como rolar iniciativa, ataque, dano, morte) vêm do **BookIndex** via `lookup_rules` e interpretação do LLM. O servidor persiste mutações do tracker e dono dos dados.

## O que o tracker guarda

| Campo | Notas |
|---|---|
| Combatants | PC (ligado a Character) ou NPC (só no encounter) |
| Iniciativa / ordem | Ordem de turnos |
| Turn pointer | De quem é a vez |
| HP / resources / status | Opcionais — tags e números, não um DSL de regras |

## Combatant ≠ Character

- **Character** — PC do roster da Campaign.
- **Combatant** — linha no encounter (nome, lado, iniciativa, hp…); NPCs existem só aqui durante o encontro.

## Tools típicas

Mutações passam por GM Tools, por exemplo: `begin_combat`, `apply_harm`, `next_turn`, … (ver `services/play/gm/tools.py` e `combat.py`).

Rolagens de PC em combate usam **Roll Call**, não `roll_dice` imediato.

## O que foi rejeitado

- DSL completo de regras ou pipeline hit-vs-AC hardcoded em Python (impediria sistemas uploadados arbitrários).
- Tratar narração / Voice Direction como autoridade de HP.

Voice Direction **nunca** muta combate nem Campaign State.

## Distinção do manuscrito

Secções “Combat:” no Blueprint / Markdown são design de sessão. O **Combat Encounter** ativo é runtime no Campaign State.

Implementação: `services/play/gm/combat.py`.

---

[← Roll Call](13-roll-call.md) · [Índice](README.md) · [Seguinte: Realtime →](15-realtime.md)
