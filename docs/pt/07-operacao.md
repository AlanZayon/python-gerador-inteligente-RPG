# 7. Operação e segurança

## 7.1 Correr local

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # preencher AWS, Redis, NINEROUTER_KEY

python app.py            # :5000
python worker.py         # segundo terminal
```

Harness Vue: outro repositório, `FRONTEND_URL` / CORS.

9router: `NINEROUTER_URL` (ex. `http://localhost:20128/v1`), dashboard típico em `:20128/dashboard`.

> **Evidência — 9router up**  
> Caminho esperado: `docs/evidence/9router-dashboard.png`

## 7.2 Produção

`Procfile`: Gunicorn (`timeout 120`) + `python worker.py`. Dois serviços. PostgreSQL. `AUTH_DEV_MODE=false`. Clerk JWKS. `S3_DELETE_INPUTS_AFTER_PROCESS` recomendado `true`.

Worker GHA: `USE_GHA_WORKER` + cooldown; só fallback.

## 7.3 Variáveis (ver `.env.example`)

Grupos: Flask, `DATABASE_URL`, AWS/S3, Redis, 9router/LLM, Clerk, Stripe, Resend, Sentry, CORS, worker, RAG (`RAG_*`), GitHub dispatch.

Nunca commitar `.env`. PDFs e `examples/eval_runs/` estão no `.gitignore`.

## 7.4 CI

`.github/workflows/test.yml`: Python 3.11, `ruff check app.py worker.py services tasks tests`, `pytest -q`.

> **Evidência — CI verde**  
> Caminho esperado: `docs/evidence/ci-green.png`

## 7.5 Segurança

- Magic bytes PDF; `job_id` UUID
- Auth Clerk / API key; dev token bloqueado em production
- Rate limits Redis
- Webhook Stripe assinado + eventos idempotentes
- Erros opacos em production
- Refund de créditos se o worker falha após o debit
- Índices FAISS e PDFs **locais** — não vão no git

## 7.6 Observabilidade

Logs stdout (`%(asctime)s %(name)s %(levelname)s`). Sentry opcional (`SENTRY_DSN`). Health: `/health/ready`, `/status`.
