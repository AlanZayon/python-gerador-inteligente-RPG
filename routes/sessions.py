"""GameSession HTTP routes."""

from flask import Blueprint, g, jsonify, request

from services.auth import require_user
from services.play.sessions import (
    SessionError,
    claim_character,
    create_game_session,
    end_game_session,
    get_session_for_user,
    join_game_session,
    session_to_dict,
    set_ready,
    start_game_session,
)
from services.play.gm import ActionError, resolve_gm_llm, submit_player_action
from services.play.sync import SyncError, get_reconnect_snapshot

sessions_bp = Blueprint("sessions", __name__, url_prefix="/sessions")


def _error(exc: SessionError | ActionError | SyncError):
    status = {
        "not_found": 404,
        "forbidden": 403,
        "full": 409,
        "session_exists": 409,
        "character_taken": 409,
        "not_ready": 400,
        "invalid": 400,
    }.get(exc.code, 400)
    return jsonify({"error": exc.code, "message": exc.message}), status


@sessions_bp.route("", methods=["POST"])
@require_user
def create_session():
    body = request.get_json(silent=True) or {}
    campaign_id = (body.get("campaign_id") or "").strip()
    if not campaign_id:
        return jsonify({"error": "campaign_id is required"}), 400
    try:
        gs = create_game_session(g.user.id, campaign_id)
    except SessionError as exc:
        return _error(exc)
    return jsonify({"success": True, "session": session_to_dict(gs)}), 201


@sessions_bp.route("/join", methods=["POST"])
@require_user
def join_session():
    body = request.get_json(silent=True) or {}
    invite_code = (body.get("invite_code") or "").strip()
    if not invite_code:
        return jsonify({"error": "invite_code is required"}), 400
    try:
        sp = join_game_session(g.user.id, invite_code)
        gs = get_session_for_user(g.user.id, sp.game_session_id)
    except SessionError as exc:
        return _error(exc)
    return jsonify({"success": True, "session": session_to_dict(gs)})


@sessions_bp.route("/<session_id>", methods=["GET"])
@require_user
def get_session(session_id: str):
    gs = get_session_for_user(g.user.id, session_id)
    if not gs:
        return jsonify({"error": "not_found", "message": "GameSession not found"}), 404
    return jsonify({"session": session_to_dict(gs)})


@sessions_bp.route("/<session_id>/claim", methods=["POST"])
@require_user
def claim(session_id: str):
    body = request.get_json(silent=True) or {}
    character_id = (body.get("character_id") or "").strip()
    if not character_id:
        return jsonify({"error": "character_id is required"}), 400
    try:
        claim_character(g.user.id, session_id, character_id)
        gs = get_session_for_user(g.user.id, session_id)
    except SessionError as exc:
        return _error(exc)
    return jsonify({"success": True, "session": session_to_dict(gs)})


@sessions_bp.route("/<session_id>/ready", methods=["POST"])
@require_user
def ready(session_id: str):
    body = request.get_json(silent=True) or {}
    ready_flag = body.get("ready", True)
    try:
        set_ready(g.user.id, session_id, bool(ready_flag))
        gs = get_session_for_user(g.user.id, session_id)
    except SessionError as exc:
        return _error(exc)
    return jsonify({"success": True, "session": session_to_dict(gs)})


@sessions_bp.route("/<session_id>/start", methods=["POST"])
@require_user
def start(session_id: str):
    try:
        start_game_session(g.user.id, session_id)
        gs = get_session_for_user(g.user.id, session_id)
    except SessionError as exc:
        return _error(exc)
    return jsonify({"success": True, "session": session_to_dict(gs)})


@sessions_bp.route("/<session_id>/end", methods=["POST"])
@require_user
def end(session_id: str):
    try:
        end_game_session(g.user.id, session_id)
        gs = get_session_for_user(g.user.id, session_id)
    except SessionError as exc:
        return _error(exc)
    return jsonify({"success": True, "session": session_to_dict(gs)})


@sessions_bp.route("/<session_id>/snapshot", methods=["GET"])
@require_user
def snapshot(session_id: str):
    after_seq = request.args.get("after_seq", 0)
    try:
        after = int(after_seq)
    except (TypeError, ValueError):
        after = 0
    try:
        data = get_reconnect_snapshot(g.user.id, session_id, after_seq=after)
    except SyncError as exc:
        return _error(exc)
    return jsonify({"snapshot": data})


@sessions_bp.route("/<session_id>/actions", methods=["POST"])
@require_user
def submit_action(session_id: str):
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    try:
        result = submit_player_action(g.user.id, session_id, text, llm=resolve_gm_llm())
    except (SessionError, ActionError) as exc:
        return _error(exc)
    return jsonify({"success": True, **result})
