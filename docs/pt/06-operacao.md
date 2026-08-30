# 6. Operação e segurança

[← API](05-api.md) · [Índice](README.md) · [Seguinte: Avaliação →](07-avaliacao.md)

---

## Correr local

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # preencher AWS, Redis, NINEROUTER_KEY

python app.py                  # :5000
python worker.py               # segundo terminal
```

9router: `NINEROUTER_URL` (ex. `http://localhost:20128/v1`).

> **Evidência (opcional):** `docs/evidence/9router-dashboard.png`

## Produção

`Procfile`: Gunicorn (`timeout 120`) + `python worker.py` como **dois** serviços. PostgreSQL. `AUTH_DEV_MODE=false`. Clerk JWKS. Preferir `S3_DELETE_INPUTS_AFTER_PROCESS=true`. Worker via GitHub Actions é só fallback.

## Variáveis

Grupos em `.env.example`: Flask, `DATABASE_URL`, AWS/S3, Redis, 9router/LLM, Clerk, Stripe, Resend, Sentry, CORS, worker, `RAG_*`, GitHub dispatch.

Nunca commitar `.env`. PDFs e `examples/eval_runs/` estão no `.gitignore`.

## CI

`.github/workflows/test.yml`: Python 3.11, `ruff check app.py worker.py services tasks tests`, `pytest -q`.

> **Evidência (opcional):** `docs/evidence/ci-green.png`

## Segurança

- Magic bytes PDF; `job_id` UUID
- Auth Clerk / API key; dev token bloqueado em production
- Rate limits Redis
- Webhook Stripe assinado + eventos idempotentes
- Erros opacos em production
- Refund de créditos se o worker falha após o debit
- Índices FAISS e PDFs locais fora do git

## Observabilidade

Logs stdout. Sentry opcional (`SENTRY_DSN`). Health: `/health/ready`, `/status`.

Ver também: [Arquitetura](01-arquitetura.md) · [Limites](08-limites.md)

---

[← API](05-api.md) · [Índice](README.md) · [Seguinte: Avaliação →](07-avaliacao.md)
