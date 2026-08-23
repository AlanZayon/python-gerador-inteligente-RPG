# 6. HTTP API

Flask in `app.py`. Uploads are **multipart**.

Auth: Clerk bearer JWT, or `X-API-Key`, or `AUTH_DEV_MODE` + `Bearer dev-token` (**forbidden** when `FLASK_ENV=production`).

Rate limits: 10 uploads/hour, 60 polls/min, 30 share views/min per IP.

## 6.1 Generation

### `POST /generate-campaign`

`202`. Fields: `file` (PDF), `target_language`, `complexity`, `system_preset`, `party_level`, `tone`, `theme`, `use_character_sheets`, `party_size`, `sheet_files[]`. Optional header `Idempotency-Key`.

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

### `GET /job-status/<job_id>`

Status, progress, error, presigned URL when completed.

### `POST /job-status/<job_id>/refresh-url`

### `GET /c/<slug>`

Public share, rate limited.

### Catalog (mostly unauthenticated)

`GET /system-presets`, `/campaign-complexities`, `/supported-languages`, `/health/ready`, `/status`, `/example-campaign`, `/legal/content-license`, `POST /detect-system`.

## 6.2 Dashboard `/dashboard`

JWT. Profile, job list, share, content, markdown/PDF export, API key mint, `POST .../regenerate-section`.

## 6.3 Billing `/billing`

Stripe checkout, portal, session, webhook (signature + event idempotency).

## 6.4 Dev RAG `/rag`

See [04-rag.md](04-rag.md). Not the product auth model.

> **Evidence — 202 + poll**  
> Expected path: `docs/evidence/job-status-json.png`
