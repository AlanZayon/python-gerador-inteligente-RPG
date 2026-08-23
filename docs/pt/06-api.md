# 6. API HTTP

Base: Flask em `app.py`. JSON salvo onde indicado. Upload é **multipart**.

Auth (`services/auth.py`):

1. `Authorization: Bearer` JWT Clerk (JWKS)
2. `X-API-Key` (hashes em PostgreSQL — rota dashboard de rotação)
3. `AUTH_DEV_MODE=true` + `Bearer dev-token` — **proibido** se `FLASK_ENV=production`

Rate limit Redis: 10 uploads/hora, 60 polls/min, 30 views de share/min por IP (`services/rate_limit.py`).

## 6.1 Produto — geração

### `POST /generate-campaign`

`@require_user` + rate limit. `202` no sucesso.

**multipart**

| Campo | Notas |
|---|---|
| `file` | PDF do livro (obrigatório) |
| `target_language` | default `en` |
| `complexity` | `simples` \| `mediana` \| `complexa` |
| `system_preset` | ver `/system-presets`; inválido → `generic` |
| `party_level` | texto livre |
| `tone` | texto livre |
| `theme` | texto livre (também é hook de retrieval) |
| `use_character_sheets` | bool |
| `party_size` | 1–5 |
| `sheet_files` | PDFs das fichas |

Header opcional: `Idempotency-Key`.

**202**

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

Erros típicos: 400 (não PDF / língua / complexidade / fichas), 402/403 quota, 503 Redis.

### `GET /job-status/<job_id>`

Auth opcional em dev; em produção o dono deve autenticar. Resposta: `build_api_response` — status, progresso, erro, URL pré-assinada quando `completed`.

### `POST /job-status/<job_id>/refresh-url`

Nova URL pré-assinada do Markdown.

### `GET /c/<slug>`

Campanha partilhada pública, rate limited.

### Catálogo

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

## 6.2 Dashboard (`/dashboard`)

JWT. `GET /me`, `GET /jobs`, refresh-url, share, content, export markdown/PDF, `POST /api-key`, `POST /jobs/<id>/regenerate-section`.

## 6.3 Billing (`/billing`)

Stripe: checkout, portal, session, webhook (assinatura + idempotência de evento).

## 6.4 RAG dev (`/rag`)

Ver [04-rag.md](04-rag.md). Sem o mesmo modelo de auth do produto.

> **Evidência — 202 + poll**  
> Caminho esperado: `docs/evidence/job-status-json.png`
