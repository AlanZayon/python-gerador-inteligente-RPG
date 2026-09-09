"""Campaign HTTP routes (Play Application adapters)."""

from flask import Blueprint, g, jsonify, request

from services.auth import require_user
from services.play.campaigns import (
    CampaignCreateError,
    campaign_to_dict,
    create_campaign_from_job,
    get_campaign_for_user,
)

campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/campaigns")


@campaigns_bp.route("", methods=["POST"])
@require_user
def create_campaign():
    body = request.get_json(silent=True) or {}
    job_id = (body.get("job_id") or "").strip()
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400
    try:
        campaign = create_campaign_from_job(g.user.id, job_id)
    except CampaignCreateError as exc:
        status = 404 if exc.code == "not_found" else 400
        if exc.code == "forbidden":
            status = 403
        return jsonify({"error": exc.code, "message": exc.message}), status
    return jsonify({"success": True, "campaign": campaign_to_dict(campaign)}), 201


@campaigns_bp.route("/<campaign_id>", methods=["GET"])
@require_user
def get_campaign(campaign_id: str):
    campaign = get_campaign_for_user(g.user.id, campaign_id)
    if not campaign:
        return jsonify({"error": "not_found", "message": "Campaign not found"}), 404
    return jsonify({"campaign": campaign_to_dict(campaign)})
