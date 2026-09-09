"""WebSocket gateway for GameSession sync (single-instance; ADR 0005)."""

from __future__ import annotations

import json
import logging
import os
import uuid

from flask import request
from flask_sock import Sock

from services.auth import (
    _auth_dev_mode,
    _clerk_configured,
    _verify_clerk_token,
    resolve_auth_context,
)
from services.play import hub as hub_module
from services.play.gm import MockGMLLM, submit_player_action
from services.play.sync import SyncError, get_reconnect_snapshot, set_presence
from services.users import get_or_create_user

logger = logging.getLogger(__name__)

sock = Sock()


def _auth_user_from_ws():
    token = (request.args.get("token") or "").strip()
    ctx = None
    if token:
        if _auth_dev_mode() and token == "dev-token":
            ctx = {
                "clerk_id": os.getenv("AUTH_DEV_USER_ID", "dev-user-001"),
                "email": os.getenv("AUTH_DEV_EMAIL", "dev@arcane-forge.local"),
            }
        elif _clerk_configured():
            payload = _verify_clerk_token(token)
            if payload:
                ctx = {
                    "clerk_id": payload.get("sub"),
                    "email": payload.get("email") or payload.get("primary_email") or "",
                }
        elif _auth_dev_mode():
            ctx = {"clerk_id": token, "email": f"{token}@dev.local"}
    if not ctx:
        ctx = resolve_auth_context()
    if not ctx or not ctx.get("clerk_id"):
        return None
    return get_or_create_user(ctx["clerk_id"], ctx.get("email", ""))


def register_session_sockets(app):
    sock.init_app(app)

    @sock.route("/ws/sessions/<session_id>")
    def session_socket(ws, session_id: str):
        user = _auth_user_from_ws()
        if not user:
            ws.send(json.dumps({"version": 1, "type": "error", "payload": {"code": "unauthorized"}}))
            return

        after_seq = int(request.args.get("after_seq") or 0)
        conn_id = str(uuid.uuid4())

        try:
            snapshot = get_reconnect_snapshot(user.id, session_id, after_seq=after_seq)
        except SyncError as exc:
            ws.send(
                json.dumps(
                    {
                        "version": 1,
                        "type": "error",
                        "payload": {"code": exc.code, "message": exc.message},
                    }
                )
            )
            return

        def send(envelope: dict):
            try:
                ws.send(json.dumps(envelope))
            except Exception:
                pass

        hub_module.default_hub.subscribe(session_id, conn_id, user.id, send)
        try:
            if hub_module.default_hub.user_connection_count(session_id, user.id) == 1:
                set_presence(user.id, session_id, connected=True)
            # Refresh snapshot after presence so reconnect clients see connected=true
            snapshot = get_reconnect_snapshot(user.id, session_id, after_seq=after_seq)
            ws.send(
                json.dumps(
                    {
                        "version": 1,
                        "type": "snapshot",
                        "session_id": session_id,
                        "payload": snapshot,
                    }
                )
            )
            while True:
                raw = ws.receive()
                if raw is None:
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                mtype = msg.get("type")
                if mtype == "ping":
                    ws.send(json.dumps({"version": 1, "type": "pong"}))
                elif mtype == "player_action":
                    text = (msg.get("text") or "").strip()
                    if not text:
                        continue
                    try:
                        submit_player_action(user.id, session_id, text, llm=MockGMLLM())
                    except Exception as exc:  # noqa: BLE001
                        ws.send(
                            json.dumps(
                                {
                                    "version": 1,
                                    "type": "error",
                                    "payload": {
                                        "code": getattr(exc, "code", "action_failed"),
                                        "message": str(exc),
                                    },
                                }
                            )
                        )
        finally:
            left_user = hub_module.default_hub.unsubscribe(session_id, conn_id)
            if left_user:
                try:
                    set_presence(left_user, session_id, connected=False)
                except SyncError:
                    pass
