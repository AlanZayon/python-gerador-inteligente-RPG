"""Dashboard and account routes."""

import hashlib
import os
import secrets

from flask import Blueprint, g, jsonify, request, Response

from database import SessionLocal
from models.entities import User
from services.auth import require_user
from services.campaign_parse import build_job_meta, extract_title, slugify_title
from services.jobs_db import get_job_for_user, list_user_jobs, set_job_share
from services.quota import CREDIT_COSTS
from services.s3_storage import fetch_s3_text, generate_presigned_url
from services.job_status import get_status, save_result, save_status
from services.pdf_export import campaign_markdown_to_pdf
from services.quota import check_and_deduct, QuotaError, quota_error_response
from tasks.campaign_tasks import regenerate_section
from services.s3_storage import upload_content_to_s3
import json
from services.users import PLAN_CREDITS

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/me", methods=["GET"])
@require_user
def get_me():
    plan = g.user.plan
    return jsonify({
        "id": g.user.id,
        "email": g.user.email,
        "plan": plan,
        "credits_balance": g.user.credits_balance,
        "plan_credits_monthly": PLAN_CREDITS.get(plan, 1),
        "credit_costs": CREDIT_COSTS,
        "has_stripe": bool(g.user.stripe_customer_id),
        "has_api_key": bool(g.user.api_key_hash),
    })


@dashboard_bp.route("/jobs", methods=["GET"])
@require_user
def get_jobs():
    jobs = list_user_jobs(g.user.id)
    return jsonify({
        "jobs": [
            {
                "id": j.id,
                "status": j.status,
                "complexity": j.complexity,
                "language": j.language,
                "filename": j.filename,
                "credits_charged": j.credits_charged,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "share_slug": j.share_slug if j.share_public else None,
                "use_character_sheets": j.use_character_sheets,
                "party_size": j.party_size,
            }
            for j in jobs
        ],
    })


@dashboard_bp.route("/jobs/<job_id>/refresh-url", methods=["POST"])
@require_user
def refresh_job_url(job_id):
    job = get_job_for_user(job_id, g.user.id)
    if not job or job.status != "completed":
        return jsonify({"error": "Campaign not found or not completed"}), 404
    s3_key = job.campaign_s3_key
    if not s3_key:
        status_data = get_status(job_id)
        s3_key = (status_data.get("data") or {}).get("s3_key") if status_data else None
    if not s3_key:
        return jsonify({"error": "S3 key not found"}), 404
    url = generate_presigned_url(s3_key)
    return jsonify({"job_id": job_id, "campaign_url": url})


@dashboard_bp.route("/jobs/<job_id>/share", methods=["POST"])
@require_user
def share_job(job_id):
    if g.user.plan not in ("pro", "studio"):
        return jsonify({"error": "Share links require Pro or Studio plan", "upgrade_url": "/pricing"}), 402
    slug = secrets.token_urlsafe(8)[:12]
    if not set_job_share(job_id, g.user.id, slug, True):
        return jsonify({"error": "Cannot share this campaign"}), 400
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return jsonify({"share_slug": slug, "share_url": f"{frontend.rstrip('/')}/c/{slug}"})


def _load_completed_campaign(job_id: str, user_id: str):
    job = get_job_for_user(job_id, user_id)
    if not job or job.status != "completed" or not job.campaign_s3_key:
        return None, None
    content = fetch_s3_text(job.campaign_s3_key)
    if not content:
        return job, None
    return job, content


@dashboard_bp.route("/jobs/<job_id>/content", methods=["GET"])
@require_user
def get_job_content(job_id):
    job, content = _load_completed_campaign(job_id, g.user.id)
    if not job:
        return jsonify({"error": "Campaign not available"}), 404
    if not content:
        return jsonify({"error": "Could not load campaign content"}), 404
    status_data = get_status(job_id)
    redis_result = (status_data or {}).get("data") or {}
    return jsonify({
        "content": content,
        "meta": build_job_meta(job, content, redis_result),
    })


@dashboard_bp.route("/jobs/<job_id>/export/markdown", methods=["GET"])
@require_user
def export_markdown(job_id):
    job, content = _load_completed_campaign(job_id, g.user.id)
    if not job:
        return jsonify({"error": "Campaign not available"}), 404
    if not content:
        return jsonify({"error": "Could not load campaign content"}), 404
    title = extract_title(content)
    filename = f"{slugify_title(title)}.md"
    return Response(
        content,
        mimetype="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@dashboard_bp.route("/jobs/<job_id>/export/pdf", methods=["GET"])
@require_user
def export_pdf(job_id):
    if g.user.plan not in ("pro", "studio"):
        return jsonify({"error": "PDF export requires Pro or Studio plan"}), 402
    job, content = _load_completed_campaign(job_id, g.user.id)
    if not job:
        return jsonify({"error": "Campaign not available"}), 404
    if not content:
        return jsonify({"error": "Could not load campaign content"}), 404
    status_data = get_status(job_id)
    redis_result = (status_data or {}).get("data") or {}
    meta = build_job_meta(job, content, redis_result)
    pdf_bytes = campaign_markdown_to_pdf(content, meta.get("title") or job.filename or "Campaign", job.language, meta)
    if not pdf_bytes:
        return jsonify({"error": "PDF generation unavailable"}), 503
    title_slug = slugify_title(meta.get("title") or "campaign")
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{title_slug}.pdf"'},
    )


@dashboard_bp.route("/api-key", methods=["POST"])
@require_user
def generate_api_key():
    if g.user.plan != "studio":
        return jsonify({"error": "API access requires Studio plan"}), 402
    raw_key = f"af_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == g.user.id).first()
        u.api_key_hash = key_hash
        db.commit()
    finally:
        db.close()
    return jsonify({"api_key": raw_key, "message": "Store this key securely; it won't be shown again."})


@dashboard_bp.route("/jobs/<job_id>/regenerate-section", methods=["POST"])
@require_user
def regenerate_section_endpoint(job_id):
    body = request.get_json(silent=True) or {}
    section = body.get("section", "sessions")
    instructions = body.get("instructions", "Expand with more detail")

    job = get_job_for_user(job_id, g.user.id)
    if not job or job.status != "completed" or not job.campaign_s3_key:
        return jsonify({"error": "Campaign not available"}), 404

    try:
        check_and_deduct(g.user, "simples", job_id)
    except QuotaError as exc:
        return quota_error_response(exc)

    content = fetch_s3_text(job.campaign_s3_key)
    if not content:
        return jsonify({"error": "Could not load campaign"}), 404

    status_data = get_status(job_id)
    result = (status_data or {}).get("data") or {}
    book_bible_raw = result.get("book_bible")
    if isinstance(book_bible_raw, str):
        try:
            book_bible = json.loads(book_bible_raw)
        except Exception:
            book_bible = {}
    elif isinstance(book_bible_raw, dict):
        book_bible = book_bible_raw
    else:
        book_bible = {}

    try:
        new_section = regenerate_section(
            book_bible=book_bible,
            current_content=content,
            section=section,
            instructions=instructions,
            target_language=job.language,
            system_preset=job.system_preset,
        )
        updated = content + f"\n\n## Regenerated: {section}\n\n{new_section}\n"
        upload_result = upload_content_to_s3(updated, job.campaign_s3_key.split("/")[-1])
        preview = updated[:500] + "..." if len(updated) > 500 else updated
        result_patch = {
            "campaign_url": upload_result["file_url"],
            "s3_key": upload_result["s3_key"],
            "preview": preview,
            "file_size": len(updated),
        }
        status_data = get_status(job_id) or {}
        existing = status_data.get("data") or {}
        merged = {**existing, **result_patch}
        save_result(job_id, merged)
        save_status(job_id, "completed", merged)
        return jsonify({
            "success": True,
            "section": section,
            "preview": new_section[:500],
            "content_length": len(updated),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
