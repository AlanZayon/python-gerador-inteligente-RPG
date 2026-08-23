# 7. Operations and security

## 7.1 Local run

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

python app.py
python worker.py
```

Vue harness is a **separate** repo. Point `FRONTEND_URL` / CORS at it.

> **Evidence — 9router up**  
> Expected path: `docs/evidence/9router-dashboard.png`

## 7.2 Production

Procfile: Gunicorn (`timeout 120`) + `python worker.py` as **two** services. PostgreSQL. `AUTH_DEV_MODE=false`. Clerk JWKS. Prefer deleting S3 inputs after process. GHA worker is fallback only.

## 7.3 Configuration

See `.env.example`: Flask, `DATABASE_URL`, AWS, Redis, 9router/LLM, Clerk, Stripe, Resend, Sentry, CORS, worker, `RAG_*`, GitHub dispatch. Never commit `.env`. Rulebook PDFs and `examples/eval_runs/` are gitignored.

## 7.4 CI

Python 3.11, `ruff check app.py worker.py services tasks tests`, `pytest -q`.

> **Evidence — green CI**  
> Expected path: `docs/evidence/ci-green.png`

## 7.5 Security

PDF magic bytes; UUID job ids; Clerk/API keys; production blocks dev auth; Redis rate limits; signed Stripe webhooks; opaque 500s in production; credit refund on worker failure; FAISS/PDFs stay off git.

## 7.6 Observability

Stdout logging, optional Sentry, `/health/ready` and `/status`.
