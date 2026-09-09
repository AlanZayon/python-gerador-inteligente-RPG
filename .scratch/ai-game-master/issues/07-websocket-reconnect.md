# 07: WebSocket sync + reconnect

**What to build:** Clients connect to the GameSession over WebSocket, receive lobby and play events (join/leave, claims, GM narration, state patches, dice results), and on reconnect get current Campaign State plus missed events. Single-instance API assumption is documented; authority remains in the database.

**Blocked by:** 06 — Text GM turn with mock LLM

**Status:** resolved

- [x] Authenticated WS join is scoped to GameSession membership
- [x] Versioned events are broadcast for lobby and GM turn outcomes
- [x] Reconnect restores snapshot and missed events without relying on process-only memory
- [x] Presence join/leave is visible to connected clients
- [x] Text action path still works if WS is down (HTTP fallback or clear error)—table does not soft-lock forever
- [x] Integration test covers at least two clients or two connection lifecycles against the gateway/boundary
