# 6. Operations and security

[← API](05-api.md) · [Index](README.md) · [Next: Evaluation →](07-evaluation.md)

---

## Local run

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

python app.py
python worker.py
```

9router: `NINEROUTER_URL` (e.g. `http://localhost:20128/v1`).

> **Evidence (optional):** `docs/evidence/9router-dashboard.png`

## Production

Procfile: Gunicorn (`timeout 120`) + `python worker.py` as **two** services. PostgreSQL. `AUTH_DEV_MODE=false`. Clerk JWKS. Prefer deleting S3 inputs after process. GHA worker is fallback only.

## Configuration

See `.env.example`: Flask, `DATABASE_URL`, AWS, Redis, 9router/LLM, Clerk, Stripe, Resend, Sentry, CORS, worker, `RAG_*`, GitHub dispatch. Never commit `.env`. Rulebook PDFs and `examples/eval_runs/` are gitignored.

## CI

Python 3.11, `ruff check app.py worker.py services tasks tests`, `pytest -q`.

> **Evidence (optional):** `docs/evidence/ci-green.png`

## Security

PDF magic bytes; UUID job ids; Clerk/API keys; production blocks dev auth; Redis rate limits; signed Stripe webhooks; opaque 500s in production; credit refund on worker failure; FAISS/PDFs stay off git.

## Observability

Stdout logging, optional Sentry, `/health/ready` and `/status`.

See also: [Architecture](01-architecture.md) · [Limits](08-limits.md)

---

[← API](05-api.md) · [Index](README.md) · [Next: Evaluation →](07-evaluation.md)
