# 5. HTTP API

[← Pipeline](04-pipeline.md) · [Index](README.md) · [Next: Operations →](06-operations.md)

---

Base: Flask in `app.py`. Uploads are **multipart**. Status/generation responses are JSON.

## Auth

1. `Authorization: Bearer` — Clerk JWT (JWKS)
2. `X-API-Key` — per-user key (hashed in PostgreSQL)
3. `AUTH_DEV_MODE=true` + `Bearer dev-token` — **forbidden** when `FLASK_ENV=production`

Rate limits: 10 uploads/hour, 60 polls/min, 30 share views/min per IP.

## Generation

### `POST /generate-campaign`

`202` on success. Fields: `file` (PDF), `target_language`, `complexity`, `system_preset`, `party_level`, `tone`, `theme`, `use_character_sheets`, `party_size`, `sheet_files[]`. Optional header `Idempotency-Key`.

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

## Catalog

| Method | Path | Auth |
|---|---|---|
| GET | `/system-presets` | no |
| GET | `/campaign-complexities` | no |
| GET | `/supported-languages` | no |
| GET | `/health/ready` | no (DB + Redis) |
| GET | `/status` | no |
| GET | `/example-campaign` | no |
| GET | `/legal/content-license` | no |
| POST | `/detect-system` | per app |

## Dashboard `/dashboard`

JWT. Profile, jobs, share, content, markdown/PDF export, API key mint, `POST .../regenerate-section`.

## Billing `/billing`

Stripe checkout, portal, session, webhook (signature + event idempotency).

## Dev RAG `/rag`

See [RAG](03-rag.md). Not the product auth model.

> **Evidence (optional):** `docs/evidence/job-status-json.png`

See also: [Job](02-job.md) · [Operations](06-operations.md)

---

[← Pipeline](04-pipeline.md) · [Index](README.md) · [Next: Operations →](06-operations.md)
