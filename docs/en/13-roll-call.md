# 13. Roll Call

[← GM Runtime](12-gm-runtime.md) · [Index](README.md) · [Next: Combat →](14-combat.md)

---

Player Character checks are a **two-beat** table ritual ([ADR 0007](../adr/0007-pc-roll-call-confirmation.md)):

1. The Game Master Runtime consults the BookIndex (`lookup_rules`), issues a **Roll Call**, and waits.
2. The targeted Player **authorizes** the roll in the UI; the server produces the total with `DiceRng`.

The client does **not** generate the result. Confirming is not rolling.

## Why

- Player agency at the table (timing / alternative choice).
- Auditable, server-authoritative dice.
- Immediate `roll_dice` remains only for hidden GM/NPC rolls.

Accepted cost: a second serialized flight and a blocked action queue while a Roll Call is pending.

## Alternatives

A Roll Call may offer alternative checks (e.g. Perception **or** Stealth) as a list of `{skill, notation, dc}`. The Player chooses which to confirm; RNG stays on the server. Do not mash “or/ou” into the skill name.

## Cycle

```text
GM tool: request_roll
    → pending Roll Call in Campaign State
    → UI asks the Character’s Player to confirm
    → confirm_roll (WebSocket / API)
    → server DiceRng → total + success/failure
    → second GM flight with the result
```

## Practical rules

| Do | Avoid |
|---|---|
| `request_roll` for PC checks (including combat) | `roll_dice` / `perform_check` for PCs |
| RNG only on the server | Browser RNG |
| Alternatives as a structured list | “Perception or Stealth” in one skill string |

Code: `request_roll` / resolution in `services/play/gm/tools.py`; confirmation via `confirm_roll` in `routes/ws_sessions.py`.

---

[← GM Runtime](12-gm-runtime.md) · [Index](README.md) · [Next: Combat →](14-combat.md)
