from flask import Flask, request, jsonify, g
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import requests
import os
import logging
import uuid
import json
import redis
from datetime import datetime

from database import check_database_connection, init_db
from tasks.campaign_tasks import is_llm_configured
from examples.campaign_samples import get_sample_campaign
from services.s3_storage import upload_pdf_to_s3, upload_pdf_with_key, generate_presigned_url, fetch_s3_text, s3_configured
from services.redis_client import (
    PENDING_JOBS_QUEUE,
    PRIORITY_JOBS_QUEUE,
    create_redis_client,
    get_redis_url,
)
from services.job_status import build_api_response, get_status, save_status
from services.auth import require_user, optional_user, resolve_auth_context, validate_production_auth_config
from services.rate_limit import redis_rate_limit
from services.validation import (
    is_valid_job_id,
    validate_complexity,
    validate_language,
    validate_pdf_magic_bytes,
)
from services.quota import QuotaError, check_and_deduct, quota_error_response, plan_allows_character_sheets
from services.jobs_db import create_job_record, get_job_for_user, get_job_by_share_slug
from services.legal_content import CONTENT_LICENSE
from services.system_presets import SYSTEM_PRESETS
from services.sheet_validation import (
    clamp_party_size,
    parse_use_character_sheets,
    validate_sheet_file_count,
    validate_sheet_file_size,
)
from services.sentry_init import init_sentry
from routes.billing import billing_bp
from routes.dashboard import dashboard_bp
from routes.rag import rag_bp

load_dotenv()
validate_production_auth_config()
init_sentry()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

IS_PRODUCTION = os.getenv("FLASK_ENV", "").lower() == "production"
USE_GHA_WORKER = os.getenv("USE_GHA_WORKER", "false").lower() == "true"
GHA_DISPATCH_COOLDOWN = int(os.getenv("GHA_DISPATCH_COOLDOWN", "300"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
LLM_CONFIGURED = is_llm_configured()

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,https://pdf-translate-vue.vercel.app",
).split(",")

app = Flask(__name__)
CORS(app, origins=[o.strip() for o in CORS_ORIGINS if o.strip()])
app.register_blueprint(billing_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(rag_bp, url_prefix="/rag")

UPLOAD_FOLDER = 'uploads/'
CAMPAIGN_FOLDER = 'campaigns/'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CAMPAIGN_FOLDER'] = CAMPAIGN_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

redis_conn = None

try:
    init_db()
    logger.info("Database initialized")
except Exception as e:
    logger.warning("Database init failed: %s", e)

try:
    redis_conn = create_redis_client(decode_responses=False)
    redis_conn.ping()
    logger.info("Redis conectado: %s", get_redis_url())
except redis.ConnectionError as e:
    logger.warning("Redis não disponível: %s", e)
except Exception as e:
    logger.warning("Erro ao conectar ao Redis: %s", e)

for folder in [UPLOAD_FOLDER, CAMPAIGN_FOLDER]:
    os.makedirs(folder, exist_ok=True)


def _error_message(exc: Exception) -> str:
    if IS_PRODUCTION:
        return "Internal server error"
    return str(exc)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _queue_for_plan(plan: str) -> str:
    return PRIORITY_JOBS_QUEUE if plan in ("pro", "studio") else PENDING_JOBS_QUEUE


def trigger_worker() -> None:
    if not USE_GHA_WORKER:
        logger.info("GHA worker desabilitado (USE_GHA_WORKER=false). Use worker persistente.")
        return

    owner = os.getenv("GITHUB_REPO_OWNER")
    repo = os.getenv("GITHUB_REPO_NAME")
    workflow = os.getenv("GITHUB_WORKFLOW_FILE", "campaign_worker.yml")
    branch = os.getenv("GITHUB_BRANCH", "main")
    token = os.getenv("GITHUB_TOKEN")

    if not all([owner, repo, workflow, token]):
        logger.warning("Variáveis de ambiente do GitHub não configuradas")
        return

    if redis_conn is not None:
        try:
            last_dispatch = redis_conn.get("rpg:gha_last_dispatch")
            if last_dispatch:
                elapsed = datetime.utcnow().timestamp() - float(last_dispatch)
                if elapsed < GHA_DISPATCH_COOLDOWN:
                    logger.info("GHA dispatch throttled (%.0fs restantes)", GHA_DISPATCH_COOLDOWN - elapsed)
                    return
        except Exception as exc:
            logger.warning("Erro ao verificar throttle GHA: %s", exc)

    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/"
        f"actions/workflows/{workflow}/dispatches"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.post(url, headers=headers, json={"ref": branch}, timeout=30)

    if response.status_code not in (200, 204):
        logger.error("Falha ao disparar worker: %s - %s", response.status_code, response.text)
        response.raise_for_status()

    if redis_conn is not None:
        try:
            redis_conn.set("rpg:gha_last_dispatch", str(datetime.utcnow().timestamp()))
            redis_conn.expire("rpg:gha_last_dispatch", GHA_DISPATCH_COOLDOWN)
        except Exception:
            pass

    logger.info("Worker do GitHub Actions disparado com sucesso")


def _verify_job_access(job_id: str) -> tuple[dict | None, tuple | None]:
    """Return (status_data, error_response) — error_response is (json, code)."""
    status_data = get_status(job_id)
    if not status_data:
        db_job = get_job_for_user(job_id, g.user.id if g.user else None)
        if not db_job:
            return None, (jsonify({'error': 'Job not found'}), 404)
        status_data = {"status": db_job.status}

    if g.user:
        db_job = get_job_for_user(job_id, g.user.id)
        if not db_job:
            return None, (jsonify({'error': 'Access denied'}), 403)
    elif IS_PRODUCTION:
        return None, (jsonify({'error': 'Authentication required'}), 401)

    return status_data, None


@app.route('/generate-campaign', methods=['POST'])
@require_user
@redis_rate_limit(max_calls=10, window=3600, prefix="rl:upload")
def generate_campaign():
    logger.info("Recebendo requisição de geração de campanha...")
    input_pdf = None
    sheet_temp_paths: list[str] = []

    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': 'Unsupported file type. PDF only.'}), 400

        target_language = request.form.get('target_language', 'en')
        campaign_complexity = request.form.get('complexity', 'mediana')
        system_preset = request.form.get('system_preset', 'generic')
        party_level = request.form.get('party_level', '')
        tone = request.form.get('tone', '')
        theme = request.form.get('theme', '')
        idempotency_key = request.headers.get('Idempotency-Key')
        use_character_sheets = parse_use_character_sheets(request.form.get('use_character_sheets'))
        party_size = clamp_party_size(request.form.get('party_size')) if use_character_sheets else 0
        sheet_files = request.files.getlist('sheet_files') if use_character_sheets else []

        if use_character_sheets and not plan_allows_character_sheets(g.user.plan):
            return quota_error_response(QuotaError(
                "Plan restriction",
                {
                    "error": "plan_restriction",
                    "message": "Character sheets require Pro or Studio plan.",
                    "upgrade_url": f"{FRONTEND_URL}/pricing",
                },
            ))

        if use_character_sheets:
            count_err = validate_sheet_file_count(sheet_files, party_size)
            if count_err:
                return jsonify({'error': count_err}), 400
            for sf in sheet_files:
                if not sf.filename or not allowed_file(sf.filename):
                    return jsonify({'error': 'All character sheets must be PDF files'}), 400
                size_err = validate_sheet_file_size(sf)
                if size_err:
                    return jsonify({'error': size_err}), 400

        if idempotency_key:
            from services.jobs_db import find_idempotent_job
            existing = find_idempotent_job(g.user.id, idempotency_key)
            if existing:
                return jsonify({
                    'success': True,
                    'job_id': existing.id,
                    'status': existing.status,
                    'message': 'Existing job returned (idempotent)',
                }), 200

        if not validate_language(target_language):
            return jsonify({'error': 'Unsupported language'}), 400
        if not validate_complexity(campaign_complexity):
            return jsonify({'error': 'Complexity must be: simples, mediana or complexa'}), 400
        if system_preset not in SYSTEM_PRESETS:
            system_preset = 'generic'

        job_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        input_pdf = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
        file.save(input_pdf)

        if not validate_pdf_magic_bytes(input_pdf):
            os.remove(input_pdf)
            return jsonify({'error': 'File is not a valid PDF'}), 400

        if use_character_sheets:
            for i, sf in enumerate(sheet_files):
                sheet_name = secure_filename(sf.filename)
                sheet_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_sheet_{i}_{sheet_name}")
                sf.save(sheet_path)
                if not validate_pdf_magic_bytes(sheet_path):
                    os.remove(sheet_path)
                    for p in sheet_temp_paths:
                        if os.path.exists(p):
                            os.remove(p)
                    os.remove(input_pdf)
                    return jsonify({'error': f'Character sheet {i + 1} is not a valid PDF'}), 400
                sheet_temp_paths.append(sheet_path)

        try:
            credits_charged = check_and_deduct(g.user, campaign_complexity, job_id)
        except QuotaError as exc:
            os.remove(input_pdf)
            for p in sheet_temp_paths:
                if os.path.exists(p):
                    os.remove(p)
            return quota_error_response(exc)

        existing = create_job_record(
            job_id=job_id,
            user_id=g.user.id,
            complexity=campaign_complexity,
            language=target_language,
            filename=filename,
            credits_charged=credits_charged,
            idempotency_key=idempotency_key,
            system_preset=system_preset,
            use_character_sheets=use_character_sheets,
            party_size=party_size if use_character_sheets else 0,
        )
        if existing.id != job_id:
            if input_pdf and os.path.exists(input_pdf):
                os.remove(input_pdf)
            for p in sheet_temp_paths:
                if os.path.exists(p):
                    os.remove(p)
            return jsonify({
                'success': True,
                'job_id': existing.id,
                'status': existing.status,
                'message': 'Existing job returned (idempotent)',
            }), 200

        upload_result = upload_pdf_to_s3(input_pdf, filename)
        os.remove(input_pdf)
        input_pdf = None

        sheet_s3_keys: list[str] = []
        for i, sheet_path in enumerate(sheet_temp_paths):
            s3_key = f"sheets/{job_id}/pc_{i}.pdf"
            upload_pdf_with_key(sheet_path, s3_key)
            sheet_s3_keys.append(s3_key)
            os.remove(sheet_path)
        sheet_temp_paths.clear()

        if redis_conn is None:
            return jsonify({'error': 'Redis unavailable. Check REDIS_URL and restart the API.'}), 503

        job_key = f"rpg:job:{job_id}"
        redis_mapping = {
            "job_id": job_id,
            "user_id": g.user.id,
            "file_url": upload_result["file_url"],
            "s3_key": upload_result["s3_key"],
            "filename": filename,
            "language": target_language,
            "complexity": campaign_complexity,
            "system_preset": system_preset,
            "party_level": party_level,
            "tone": tone,
            "theme": theme,
            "credits_charged": str(credits_charged),
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
            "use_character_sheets": "true" if use_character_sheets else "false",
            "party_size": str(party_size),
            "sheet_s3_keys": json.dumps(sheet_s3_keys),
        }
        redis_conn.hset(job_key, mapping=redis_mapping)

        queue_name = _queue_for_plan(g.user.plan)
        redis_conn.rpush(queue_name, job_id)
        save_status(job_id, "queued", {"progress": "Waiting for processing...", "progress_percent": 3}, conn=create_redis_client())

        try:
            trigger_worker()
        except Exception as e:
            logger.error("Falha ao disparar worker: %s", e)

        from services.users import get_user_by_id
        fresh_user = get_user_by_id(g.user.id)
        return jsonify({
            'success': True,
            'job_id': job_id,
            'status': 'queued',
            'credits_charged': credits_charged,
            'credits_remaining': fresh_user.credits_balance if fresh_user else 0,
            'message': 'Job queued for processing',
        }), 202

    except Exception as e:
        logger.error("Erro ao iniciar geração de campanha: %s", e)
        if input_pdf and os.path.exists(input_pdf):
            try:
                os.remove(input_pdf)
            except Exception:
                pass
        for p in sheet_temp_paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        return jsonify({'error': _error_message(e)}), 500


@app.route('/job-status/<job_id>', methods=['GET'])
@optional_user
@redis_rate_limit(max_calls=60, window=60, prefix="rl:poll")
def get_job_status_endpoint(job_id):
    if not is_valid_job_id(job_id):
        return jsonify({'error': 'Invalid job ID'}), 400

    status_data, err = _verify_job_access(job_id)
    if err:
        return err

    return jsonify(build_api_response(job_id, status_data))


@app.route('/job-status/<job_id>/refresh-url', methods=['POST'])
@require_user
def refresh_campaign_url(job_id):
    if not is_valid_job_id(job_id):
        return jsonify({'error': 'Invalid job ID'}), 400

    db_job = get_job_for_user(job_id, g.user.id)
    if not db_job:
        return jsonify({'error': 'Access denied'}), 403

    status_data = get_status(job_id)
    if not status_data or status_data.get("status") != "completed":
        return jsonify({'error': 'Campaign not completed or job not found'}), 404

    result = status_data.get("data") or {}
    s3_key = result.get("s3_key") or db_job.campaign_s3_key
    if not s3_key:
        return jsonify({'error': 'S3 key not found for this job'}), 404

    new_url = generate_presigned_url(s3_key)
    updated = {**result, "campaign_url": new_url}
    save_status(job_id, "completed", updated, conn=create_redis_client())

    return jsonify({
        'job_id': job_id,
        'campaign_url': new_url,
    })


@app.route('/c/<slug>', methods=['GET'])
@redis_rate_limit(max_calls=30, window=60, prefix="rl:share")
def get_shared_campaign(slug):
    job = get_job_by_share_slug(slug)
    if not job or not job.campaign_s3_key:
        return jsonify({'error': 'Shared campaign not found'}), 404
    content = fetch_s3_text(job.campaign_s3_key)
    if not content:
        return jsonify({'error': 'Campaign content unavailable'}), 404
    return jsonify({
        'slug': slug,
        'complexity': job.complexity,
        'language': job.language,
        'content': content,
        'created_at': job.completed_at.isoformat() if job.completed_at else None,
    })


@app.route('/legal/content-license', methods=['GET'])
def get_content_license():
    return jsonify({'license': CONTENT_LICENSE})


@app.route('/system-presets', methods=['GET'])
def get_system_presets():
    return jsonify({
        k: {"id": v["id"], "name": v["name"], "description": v["description"]}
        for k, v in SYSTEM_PRESETS.items()
    })


@app.route('/health/ready', methods=['GET'])
def health_ready():
    checks = {
        "database": check_database_connection(),
        "redis": False,
        "s3": s3_configured(),
    }
    if redis_conn is not None:
        try:
            redis_conn.ping()
            checks["redis"] = True
        except Exception:
            checks["redis"] = False
    ready = checks["database"] and checks["redis"]
    return jsonify({"ready": ready, "checks": checks}), 200 if ready else 503


@app.route('/campaign-complexities', methods=['GET'])
def get_campaign_complexities():
    complexities = {
        'simples': {
            'name': 'Simple Campaign',
            'sessions': '1-2 sessions',
            'description': 'Direct story, perfect for one-shots or introductions',
            'duration': '3-8 hours total',
            'focus': 'Combat and clear objectives',
            'credits': 1,
        },
        'mediana': {
            'name': 'Medium Campaign',
            'sessions': '3-4 sessions',
            'description': 'Balance of combat, exploration, and character development',
            'duration': '9-16 hours total',
            'focus': 'Branching story and meaningful choices',
            'credits': 2,
        },
        'complexa': {
            'name': 'Complex Campaign',
            'sessions': '5+ sessions',
            'description': 'Epic arc with multiple paths and consequences',
            'duration': '17+ hours total',
            'focus': 'Deep narrative and character arcs',
            'credits': 4,
        },
    }
    return jsonify(complexities)


@app.route('/supported-languages', methods=['GET'])
def get_supported_languages():
    languages = {
        'pt': 'Português', 'en': 'English', 'es': 'Español', 'fr': 'Français',
        'de': 'Deutsch', 'it': 'Italiano', 'ja': '日本語', 'ko': '한국어',
        'zh': '中文', 'ru': 'Русский',
    }
    return jsonify(languages)


@app.route('/status', methods=['GET'])
def get_status_endpoint():
    pending_jobs = 0
    priority_jobs = 0
    if redis_conn is not None:
        try:
            pending_jobs = redis_conn.llen(PENDING_JOBS_QUEUE)
            priority_jobs = redis_conn.llen(PRIORITY_JOBS_QUEUE)
        except Exception as e:
            logger.warning("Erro ao consultar fila Redis: %s", e)

    return jsonify({
        'status': 'online',
        'service': 'Arcane Forge',
        'supported_formats': list(ALLOWED_EXTENSIONS),
        'max_file_size_mb': MAX_FILE_SIZE // (1024 * 1024),
        'llm_configured': LLM_CONFIGURED,
        'gemini_configured': LLM_CONFIGURED,
        'redis_connected': redis_conn is not None,
        'queue_status': {
            'pending_jobs': pending_jobs,
            'priority_jobs': priority_jobs,
        },
    })


@app.route('/example-campaign', methods=['GET'])
def get_example_campaign():
    try:
        complexity = request.args.get('complexity', 'mediana')
        language = request.args.get('language', 'en')
        if not validate_complexity(complexity):
            return jsonify({'error': 'Invalid complexity'}), 400
        if not validate_language(language):
            return jsonify({'error': 'Invalid language'}), 400

        example = get_sample_campaign(complexity, language)
        if not example:
            return jsonify({'error': 'No sample available'}), 404
        return jsonify({
            'success': True,
            'complexity': complexity,
            'language': language,
            'content': example,
            'message': 'Demo sample campaign',
            'is_demo': True,
        })
    except Exception as e:
        logger.error("Erro ao gerar exemplo: %s", e)
        return jsonify({'error': 'Error generating example'}), 500


@app.route('/detect-system', methods=['POST'])
@require_user
@redis_rate_limit(max_calls=20, window=3600, prefix="rl:detect")
def detect_system():
    """Suggest system preset from uploaded PDF excerpt."""
    from services.system_detect import detect_system_preset
    from tasks.campaign_tasks import extract_text_from_pdf, validate_pdf

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"detect_{uuid.uuid4()}.pdf")
    try:
        file.save(temp_path)
        if not validate_pdf_magic_bytes(temp_path):
            return jsonify({'error': 'Invalid PDF'}), 400
        is_valid, msg = validate_pdf(temp_path)
        if not is_valid:
            return jsonify({'error': msg}), 400
        text = extract_text_from_pdf(temp_path)
        preset = detect_system_preset(text)
        return jsonify({'preset': preset, 'detected': preset is not None})
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == '__main__':
    logger.info("Arcane Forge API started")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
