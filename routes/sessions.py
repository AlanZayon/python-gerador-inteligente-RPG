"""GameSession HTTP routes."""

from flask import Blueprint, current_app, g, jsonify, request

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
from services.play.gm import ActionError, confirm_roll, resolve_gm_llm, submit_player_action
from services.play.gm.opening import deliver_session_opening
from services.play.sync import SyncError, get_reconnect_snapshot
from services.play.voice_actions import submit_voice_action
from services.voice import resolve_stt, resolve_tts

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
        "stt_failed": 502,
        "timeout": 504,
        "rate_limited": 429,
        "awaiting_roll": 409,
        "needs_choice": 409,
        "not_your_turn": 409,
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

    opening_text = None
    try:
        import json as _json

        from database import SessionLocal
        from models.entities import GameEvent

        db = SessionLocal()
        try:
            ev = (
                db.query(GameEvent)
                .filter(
                    GameEvent.game_session_id == session_id,
                    GameEvent.type == "gm_narration",
                )
                .order_by(GameEvent.seq.desc())
                .first()
            )
            if ev:
                payload = _json.loads(ev.payload_json or "{}")
                opening_text = payload.get("text")
        finally:
            db.close()
    except Exception:
        opening_text = None
    return jsonify({"success": True, "session": session_to_dict(gs), "opening": opening_text})


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
    speak = body.get("speak", False)
    try:
        result = submit_player_action(
            g.user.id,
            session_id,
            text,
            llm=resolve_gm_llm(),
            tts=resolve_tts(),
            speak=bool(speak),
        )
    except (SessionError, ActionError) as exc:
        return _error(exc)
    return jsonify({"success": True, **result})


@sessions_bp.route("/<session_id>/rolls/confirm", methods=["POST"])
@require_user
def submit_roll_confirm(session_id: str):
    body = request.get_json(silent=True) or {}
    pending_id = (body.get("pending_id") or "").strip() or None
    speak = body.get("speak", False)
    chosen_skill = (body.get("chosen_skill") or "").strip() or None
    chosen_index = body.get("chosen_index")
    try:
        result = confirm_roll(
            g.user.id,
            session_id,
            pending_id=pending_id,
            llm=resolve_gm_llm(),
            tts=resolve_tts(),
            speak=bool(speak),
            chosen_skill=chosen_skill,
            chosen_index=chosen_index,
        )
    except (SessionError, ActionError) as exc:
        return _error(exc)
    return jsonify({"success": True, **result})


@sessions_bp.route("/<session_id>/actions/voice", methods=["POST"])
@require_user
def submit_voice(session_id: str):
    upload = request.files.get("audio") or request.files.get("file")
    if not upload:
        return jsonify({"error": "audio file is required"}), 400
    audio = upload.read()
    content_type = (upload.mimetype or request.form.get("content_type") or "audio/webm").strip()
    speak = request.form.get("speak", "true").strip().lower() not in {"0", "false", "no"}
    try:
        result = submit_voice_action(
            g.user.id,
            session_id,
            audio=audio,
            content_type=content_type,
            stt=resolve_stt(),
            tts=resolve_tts(),
            llm=resolve_gm_llm(),
            speak=speak,
        )
    except (SessionError, ActionError) as exc:
        return _error(exc)
    return jsonify({"success": True, **result})
