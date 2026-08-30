# 5. API HTTP

[← Pipeline](04-pipeline.md) · [Índice](README.md) · [Seguinte: Operação →](06-operacao.md)

---

Base: Flask em `app.py`. Upload é **multipart**. Respostas de status/geração são JSON.

## Auth

`services/auth.py`, por ordem:

1. `Authorization: Bearer` — JWT Clerk (JWKS)
2. `X-API-Key` — chave por utilizador (hash em PostgreSQL)
3. `AUTH_DEV_MODE=true` + `Bearer dev-token` — **proibido** se `FLASK_ENV=production`

Rate limit Redis: 10 uploads/hora, 60 polls/min, 30 views de share/min por IP.

## Geração

### `POST /generate-campaign`

`@require_user` · `202` no sucesso.

| Campo multipart | Notas |
|---|---|
| `file` | PDF do livro (obrigatório) |
| `target_language` | default `en` |
| `complexity` | `simples` \| `mediana` \| `complexa` |
| `system_preset` | ver `GET /system-presets`; inválido → `generic` |
| `party_level` | texto livre |
| `tone` | texto livre |
| `theme` | texto livre (também é hook de retrieval) |
| `use_character_sheets` | bool |
| `party_size` | 1–5 |
| `sheet_files` | PDFs das fichas |

Header opcional: `Idempotency-Key`.

```json
{
  "success": true,
  "job_id": "uuid",
  "status": "queued",
  "credits_charged": 2,
  "credits_remaining": 10,
  "message": "Job queued for processing"
}
```

Erros típicos: `400` (PDF/língua/complexidade/fichas), quota, `503` Redis.

### `GET /job-status/<job_id>`

Status, progresso, erro, URL pré-assinada quando `completed`.

### `POST /job-status/<job_id>/refresh-url`

Nova URL pré-assinada do Markdown.

### `GET /c/<slug>`

Campanha partilhada pública (rate limited).

## Catálogo

| Método | Path | Auth |
|---|---|---|
| GET | `/system-presets` | não |
| GET | `/campaign-complexities` | não |
| GET | `/supported-languages` | não |
| GET | `/health/ready` | não (DB + Redis) |
| GET | `/status` | não (saúde + fila) |
| GET | `/example-campaign` | não |
| GET | `/legal/content-license` | não |
| POST | `/detect-system` | conforme app |

## Dashboard (`/dashboard`)

JWT. `GET /me`, `GET /jobs`, refresh-url, share, content, export markdown/PDF, `POST /api-key`, `POST /jobs/<id>/regenerate-section`.

## Billing (`/billing`)

Stripe: checkout, portal, session, webhook (assinatura + idempotência de evento).

## RAG dev (`/rag`)

Ver [RAG](03-rag.md). Sem o mesmo modelo de auth do produto.

> **Evidência (opcional):** `docs/evidence/job-status-json.png`

Ver também: [Job](02-job.md) · [Operação](06-operacao.md)

---

[← Pipeline](04-pipeline.md) · [Índice](README.md) · [Seguinte: Operação →](06-operacao.md)
