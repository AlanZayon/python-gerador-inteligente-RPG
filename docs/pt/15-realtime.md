# 15. Realtime e sessão

[← Combat](14-combat.md) · [Índice](README.md) · [Seguinte: Glossário →](09-glossario.md)

---

A mesa ao vivo usa **WebSocket** no processo da API Flask para 2–4 jogadores ([ADR 0005](../adr/0005-websocket-single-instance.md)).

## Modelo de deploy

Aceitamos **instância única** (ou sticky sessions) no MVP portfolio — sem serviço realtime separado. Campaign State e eventos autoritativos vivem na **base de dados**, para reconnect e restart do processo re-sincronizarem sem depender só da memória do processo.

## GameSession

Estados típicos: **lobby** → **active** → **ended**.

No lobby, Players entram e **reclamam** Characters. Em active, ações de jogador alimentam o Game Master Runtime; presença e sync fluem pelo hub WebSocket.

## Sync e presença

| Peça | Função |
|---|---|
| Hub | Ligações WS por sessão (`services/play/hub.py`) |
| Sync | Snapshot de reconnect, presença (`services/play/sync.py`) |
| Eventos | Histórico / append (`services/play/events.py`, modelos Alembic) |

Gateway: `routes/ws_sessions.py` — auth por token na query (Clerk JWT ou `dev-token` em modo dev), depois mensagens de ação, confirmação de Roll Call, áudio GM, etc.

## Fluxo resumido

```text
Cliente Vue  ←→  WS /sessions/...  ←→  hub
                      │
                      ├─ submit_player_action → GM Runtime
                      ├─ confirm_roll → DiceRng + continuidade GM
                      └─ presença / snapshot de reconnect ← DB
```

## Limites conscientes

- Sem fan-out multi-região: um processo API (ou sticky) por mesa.
- Autoridade de jogo no servidor + DB; o cliente é projeção.

Ver também: [Play overview](11-play-overview.md) · [GM Runtime](12-gm-runtime.md) · [Voz](10-voz.md)

---

[← Combat](14-combat.md) · [Índice](README.md) · [Seguinte: Glossário →](09-glossario.md)
