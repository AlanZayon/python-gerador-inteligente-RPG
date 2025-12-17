RPG Campaign Generator API

An API that transforms RPG books (PDF) into ready-to-play campaigns using AI. It accepts a PDF upload, extracts and analyzes content, optionally uses Google Gemini to generate a complete campaign, and stores the generated campaign in Amazon S3. Processing is asynchronous, orchestrated via Redis/RQ and a worker.

Key capabilities
- Upload a PDF (RPG rulebook, module, or setting) and generate a full campaign.
- Asynchronous job orchestration using Redis and a background worker.
- Campaigns saved to S3 as Markdown with a pre-signed URL for download.
- Fallback campaign generation without Gemini for local/dev usage.
- CORS enabled for a separate frontend (local and Vercel domain are preconfigured).
- Rate limiting to protect the API.

Repository layout
- app.py — Flask API with endpoints for campaign generation, job status, and reference info.
- tasks/campaign_tasks.py — Core pipeline: download from S3, validate/extract text, AI analysis, save campaign to S3, and report job status.
- services/s3_storage.py — S3 helpers to upload source PDFs and generated Markdown campaigns and return pre-signed URLs.
- worker.py — Redis/RQ worker process.
- .github/workflows/campaign_worker.yml — Optional GitHub Actions workflow that can be triggered to run the worker remotely.
- campaigns/, job_status/, uploads/ — Local directories created on startup (used for dev/debug; main storage is S3).
- Other folders (summaries/, knowledge_base/, character_sheets/, game_rules/, cache/, processed/, translated/, accessible/, observability/) are reserved for derived artifacts and future features.

How it works
1) Client uploads a PDF to POST /generate-campaign with optional parameters language and complexity.
2) API validates the file, streams it to S3, and enqueues a job id in Redis.
3) A worker (local RQ worker or a remote runner via GitHub Actions) pulls the job, downloads the PDF from the pre-signed S3 URL, extracts text, and generates a campaign:
   - If GEMINI_API_KEY is configured, it uses Google Gemini (gemini-2.5-flash-lite).
   - Otherwise it falls back to a built-in template-based generator.
4) The generated campaign is saved back to S3 as Markdown and the job status is updated with a pre-signed URL.
5) The client polls GET /job-status/<job_id> until status is completed.

API endpoints
- POST /generate-campaign
  - Multipart form-data: file (required, PDF), target_language (default: pt), complexity (simples|mediana|complexa; default: mediana)
  - Response 202:
    {
      "success": true,
      "job_id": "<uuid>",
      "status": "queued",
      "message": "Job adicionado à fila de processamento"
    }

- GET /job-status/<job_id>
  - Returns status and (when completed) the result stored by the worker:
    {
      "job_id": "<uuid>",
      "status": "completed|processing|failed|queued",
      "last_updated": "<iso>",
      "result": {
        "campaign_url": "<S3 pre-signed URL>",
        "s3_key": "campaigns/campaign_...md",
        "preview": "First chars...",
        "file_size": 12345
      }
    }

- GET /campaign-complexities
  - Returns metadata describing the available complexities (simples, mediana, complexa).

- GET /supported-languages
  - Returns a map of language codes to human-readable names.

- GET /status
  - Health and basic service information. Includes queue info when Redis is connected.

- GET /example-campaign
  - Generates a local example without file upload using the fallback generator.
  - Query params: complexity (default: mediana), language (default: pt)

Campaign output format
- Markdown file with a standardized header and sections. When the worker uses Gemini, the content is detailed and structured; when Gemini is unavailable, a well-formed fallback campaign is produced.
- The final artifact is stored on S3 with content-type text/markdown and returned as a pre-signed URL.

Architecture overview
- Flask API (app.py)
  - Validates upload, rate-limits, and initiates async processing.
  - Uploads source PDF to S3 with a content-type application/pdf.
  - Writes a job record to Redis (rpg:pending_jobs queue + rpg:job:<id> hash) and optionally triggers a GitHub Actions workflow to run the worker.
- Worker (worker.py + tasks/campaign_tasks.py)
  - Downloads the PDF from the pre-signed S3 URL.
  - Validates the PDF (page count limits) and extracts text with PyMuPDF (fitz).
  - If GEMINI_API_KEY is configured, invokes Google Generative AI; otherwise uses a built-in fallback generator.
  - Stores the resulting Markdown on S3 and writes the completed status to a JSON file under job_status/ (dev) and/or Redis (if integrated).
- S3 integration (services/s3_storage.py)
  - Two functions: upload_pdf_to_s3 and upload_content_to_s3.
  - Returns both the S3 key and a one-hour pre-signed URL.

Prerequisites
- Python 3.10+
- Redis (local or managed) accessible by both the API and the worker.
- AWS S3 bucket and credentials.
- Optional: Google Gemini API key for higher-quality campaign generation.

Installation (local)
1) Create and activate a virtualenv
   - python -m venv venv
   - source venv/bin/activate
2) Install dependencies
   - pip install -r requirements.txt
3) Configure environment variables in .env (see below)
4) Start the API
   - python app.py
5) Start the worker in another terminal
   - python worker.py

Environment variables (.env)
Required for S3
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION (e.g., us-east-1)
- S3_BUCKET_NAME

Redis / Queue
- REDIS_URL (default: redis://localhost:6379/0)

AI (optional)
- GEMINI_API_KEY (enables Google Generative AI)

CORS / Frontend triggers (optional)
- The API is configured to allow http://localhost:5173 and https://pdf-translate-vue.vercel.app by default.

GitHub Actions (optional remote worker)
- GITHUB_REPO_OWNER
- GITHUB_REPO_NAME
- GITHUB_WORKFLOW_FILE (default: campaign_worker.yml)
- GITHUB_BRANCH (default: main)
- GITHUB_TOKEN

Running with Gunicorn (production hint)
- A simple Procfile is included. Example command:
  - web: gunicorn app:app --bind 0.0.0.0:5000 --workers 2
  - worker: python worker.py
- Ensure the API and worker can both reach the same Redis and S3.

Request examples
- curl upload (Portuguese, medium complexity)
  curl -X POST http://localhost:5000/generate-campaign \
    -F "file=@/path/to/book.pdf" \
    -F "target_language=pt" \
    -F "complexity=mediana"

- Polling job status
  curl http://localhost:5000/job-status/<job_id>

Notes and limits
- Allowed file type: PDF; max size defaults to 50 MB (see app.py MAX_CONTENT_LENGTH).
- PDF page limit: 500 (enforced in tasks/campaign_tasks.py).
- Pre-signed S3 URLs currently expire in 1 hour.
- If Redis is unavailable, the code contains a commented synchronous fallback for development; primary mode is asynchronous with Redis.

Troubleshooting
- Redis not available
  - The API logs a warning and still returns a queued response if configured with Redis-only mode. Ensure REDIS_URL is reachable and that a worker is running.
- S3 upload issues
  - Verify AWS credentials, region, and S3 bucket name. Check IAM permissions for s3:PutObject, s3:GetObject, and s3:GeneratePresignedUrl.
- Gemini errors or low-quality output
  - Ensure GEMINI_API_KEY is valid. If omitted, the fallback generator will be used.
- CORS / frontend issues
  - Update the allowed origins in app.py if your frontend runs on a different domain/port.

Security
- Do not commit secrets. Use a .env file or platform secrets management.
- Consider increasing rate limits and adding authentication if exposing the API publicly.

License
MIT