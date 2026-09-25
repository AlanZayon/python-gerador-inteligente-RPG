# 15. Realtime & session

[← Combat](14-combat.md) · [Index](README.md) · [Next: Glossary →](09-glossary.md)

---

The live table uses **WebSocket** on the Flask API process for 2–4 players ([ADR 0005](../adr/0005-websocket-single-instance.md)).

## Deploy model

We accept a **single instance** (or sticky sessions) for the portfolio MVP — no separate realtime service. Authoritative Campaign State and events live in the **database**, so reconnect and process restart can resync without relying on process memory alone.

## GameSession

Typical states: **lobby** → **active** → **ended**.

In the lobby, Players join and **claim** Characters. When active, player actions feed the Game Master Runtime; presence and sync flow through the WebSocket hub.

## Sync and presence

| Piece | Role |
|---|---|
| Hub | WS connections per session (`services/play/hub.py`) |
| Sync | Reconnect snapshot, presence (`services/play/sync.py`) |
| Events | History / append (`services/play/events.py`, Alembic models) |

Gateway: `routes/ws_sessions.py` — auth via query token (Clerk JWT or `dev-token` in dev), then action messages, Roll Call confirmation, GM audio, etc.

## Flow sketch

```text
Vue client  ←→  WS /sessions/...  ←→  hub
                      │
                      ├─ submit_player_action → GM Runtime
                      ├─ confirm_roll → DiceRng + GM continuation
                      └─ presence / reconnect snapshot ← DB
```

## Conscious limits

- No multi-region fan-out: one API process (or sticky) per table.
- Game authority on server + DB; the client is a projection.

See also: [Play overview](11-play-overview.md) · [GM Runtime](12-gm-runtime.md) · [Voice](10-voice.md)

---

[← Combat](14-combat.md) · [Index](README.md) · [Next: Glossary →](09-glossary.md)
