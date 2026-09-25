# 13. Roll Call

[← GM Runtime](12-gm-runtime.md) · [Índice](README.md) · [Seguinte: Combat →](14-combat.md)

---

Checks de Personagem (PC) são um ritual de **dois tempos** ([ADR 0007](../adr/0007-pc-roll-call-confirmation.md)):

1. O Game Master Runtime consulta o BookIndex (`lookup_rules`), emite um **Roll Call** e espera.
2. O Player alvo **autoriza** a rolagem na UI; o servidor produz o total com `DiceRng`.

O cliente **não** gera o resultado. Confirmar ≠ rolar.

## Porquê

- Agência do jogador na mesa (escolher o momento / a alternativa).
- Dados auditáveis e server-authoritative.
- `roll_dice` imediato fica só para rolagens ocultas GM/NPC.

Custo aceite: segundo flight serializado e fila de ações bloqueada enquanto houver Roll Call pendente.

## Alternativas

Um Roll Call pode oferecer checks alternativos (ex. Perception **ou** Stealth) como lista `{skill, notation, dc}`. O Player escolhe qual confirmar; o RNG continua no servidor. Não embutir “or/ou” no nome da skill.

## Ciclo

```text
GM tool: request_roll
    → pending Roll Call no Campaign State
    → UI pede confirmação ao Player do Character
    → confirm_roll (WebSocket / API)
    → DiceRng no servidor → total + sucesso/falha
    → segundo passo do GM com o resultado
```

## Regras práticas

| Fazer | Evitar |
|---|---|
| `request_roll` para checks de PC (incl. combate) | `roll_dice` / `perform_check` para PC |
| RNG só no servidor | RNG no browser |
| Alternativas como lista estruturada | Texto “Percepção ou Furtividade” numa única skill |

Código: `request_roll` / resolução em `services/play/gm/tools.py`; confirmação via `confirm_roll` em `routes/ws_sessions.py`.

---

[← GM Runtime](12-gm-runtime.md) · [Índice](README.md) · [Seguinte: Combat →](14-combat.md)
