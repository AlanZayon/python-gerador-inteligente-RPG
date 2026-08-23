# RPG Campaign Generator API

Flask API that transforms RPG rulebook PDFs into ready-to-play campaigns using a local 9router gateway (OpenAI-compatible, with template fallback). Processing is asynchronous via Redis queue and a dedicated worker process.

## Architecture

```
Frontend (Vue) → Flask API → Redis queue → worker.py → S3 + 9router
                     ↓
              PostgreSQL (users, jobs, billing)
```

- **API** (`app.py`) — upload, enqueue, job status, dashboard, billing
- **Worker** (`worker.py`) — consumes priority/standard queues, runs pipeline
- **Tasks** (`tasks/campaign_tasks.py`) — PDF extract → RAG → plan/write/revise → Markdown → S3

**Documentation (canonical):** [docs/README.md](docs/README.md) — full system manual in [Portuguese](docs/pt/README.md) and [English](docs/en/README.md). Short pipeline note: [docs/CAMPAIGN_GENERATION.md](docs/CAMPAIGN_GENERATION.md). Evidence placeholders: [docs/evidence/README.md](docs/evidence/README.md).

The Vue UI is a **demo harness** only. This repository is the product.

## Quick start (local)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env           # fill in AWS, Redis, 9router

python app.py                  # terminal 1 — API on :5000
python worker.py               # terminal 2 — job consumer
```

Frontend: see [pdf-translate-vue](../pdf-translate-vue) repo.

## Production deployment (Railway / Render)

Use the included `Procfile`:

```
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
worker: python worker.py
```

1. Create **two services**: web (Gunicorn) + worker (`python worker.py`)
2. Attach **PostgreSQL** (requires `psycopg2-binary` in requirements.txt)
3. Set all variables from `.env.example`
4. Set `USE_GHA_WORKER=false` (persistent worker recommended)
5. Set `FLASK_ENV=production` and **`AUTH_DEV_MODE=false`**
6. Configure Clerk JWT (`CLERK_JWKS_URL`, `CLERK_ISSUER`)

### Vercel frontend + API

- Configure `CORS_ORIGINS` with your Vercel URL
- Configure S3 bucket CORS to allow `GET` from your Vercel domain
- Stripe webhook → `https://your-api/billing/webhook`

## API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/generate-campaign` | JWT | Upload PDF, returns `202` + `job_id` |
| GET | `/job-status/:id` | JWT (prod) | Poll status, progress, error, result |
| POST | `/job-status/:id/refresh-url` | JWT | Regenerate expired presigned URL |
| GET | `/dashboard/me` | JWT | User profile, plan, credits |
| GET | `/dashboard/jobs` | JWT | Job history |
| POST | `/dashboard/jobs/:id/share` | JWT (Pro+) | Create public share link |
| GET | `/dashboard/jobs/:id/export/pdf` | JWT (Pro+) | Export campaign PDF |
| POST | `/billing/checkout` | JWT | Stripe checkout session |
| POST | `/billing/portal` | JWT | Stripe customer portal |
| GET | `/billing/session/:id` | JWT | Verify checkout session |
| POST | `/billing/webhook` | Stripe sig | Billing events |
| GET | `/c/:slug` | — | Public shared campaign (rate limited) |
| GET | `/health/ready` | — | Readiness probe (DB + Redis) |
| GET | `/campaign-complexities` | — | Complexity metadata |
| GET | `/supported-languages` | — | Language list |
| GET | `/status` | — | Health + queue info |
| GET | `/example-campaign` | — | Demo campaign without upload |

### Authentication

- **Primary:** Clerk JWT via `Authorization: Bearer <token>`
- **Studio API:** per-user API key via `X-API-Key` (hashed in DB)
- **Dev only:** `AUTH_DEV_MODE=true` with `Bearer dev-token` (forbidden in production)

## Environment variables

Copy `.env.example` and configure:

- **DATABASE_URL** — PostgreSQL in production, SQLite locally
- **AWS_***, **S3_BUCKET_NAME** — required for uploads
- **REDIS_URL** — required for async mode
- **CLERK_JWKS_URL**, **CLERK_ISSUER** — required in production
- **NINEROUTER_URL**, **NINEROUTER_KEY** — local 9router gateway (replaces Gemini)
- **STRIPE_*** — billing (checkout, webhook, price IDs)
- **SENTRY_DSN** — optional error tracking

## Testing

```bash
pip install -r requirements.txt
pytest -q
ruff check app.py worker.py services tasks tests routes
```

## Security

- Clerk JWT auth on protected routes; dev mode blocked in production
- Redis-backed rate limiting (10 uploads/hour, 60 polls/min, 30 share views/min per IP)
- PDF magic-byte validation, UUID job ID validation
- Stripe webhook signature verification + event idempotency
- Generic error messages in production (`FLASK_ENV=production`)

## License

MIT
