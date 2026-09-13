# WebSocket on Flask, single instance

Realtime uses WebSocket on the API process for 2–4 players. We accept a single-instance (or sticky) deployment for the portfolio MVP rather than a separate realtime service. Authoritative Campaign State and events live in the database so reconnect and process restart can resync without relying on process memory alone.
