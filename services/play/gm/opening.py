"""Session opening — GM sets the table when a GameSession becomes ACTIVE."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from database import SessionLocal
from models.entities import Campaign, CampaignCharacter, GameSession, SessionPlayer
from services.play import hub as hub_module
from services.play.events import event_to_envelope
from services.play.gm.opening_brief import build_opening_brief
from services.play.gm.provider import resolve_gm_llm
from services.play.gm.state import load_state
from services.play.gm.tools import ToolContext, execute_tool
from services.play.gm.live_llm import validate_tool_calls


logger = logging.getLogger(__name__)


def _load_manuscript_text(campaign: Campaign | None) -> str | None:
    if not campaign or not campaign.manuscript_s3_key:
        return None
    try:
        from services.s3_storage import fetch_s3_text, s3_configured

        if not s3_configured():
            return None
        return fetch_s3_text(campaign.manuscript_s3_key)
    except Exception:
        return None


def deliver_session_opening(
    session_id: str,
    *,
    llm: Any | None = None,
) -> dict:
    """Narrate the cold open and seed Campaign State. Safe to call once after start."""
    llm = llm or resolve_gm_llm()
    request_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        gs = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not gs or gs.status != "ACTIVE":
            return {"narration": None, "skipped": True}
        campaign = db.query(Campaign).filter(Campaign.id == gs.campaign_id).first()
        players = (
            db.query(SessionPlayer)
            .filter(SessionPlayer.game_session_id == session_id)
            .all()
        )
        party = []
        for sp in players:
            if not sp.character_id:
                continue
            ch = (
                db.query(CampaignCharacter)
                .filter(CampaignCharacter.id == sp.character_id)
                .first()
            )
            if ch:
                party.append({"name": ch.display_name, "character_id": ch.id})

        blueprint = {}
        if campaign and campaign.blueprint_json:
            try:
                blueprint = json.loads(campaign.blueprint_json)
            except json.JSONDecodeError:
                blueprint = {}

        opening_brief = build_opening_brief(blueprint, _load_manuscript_text(campaign))

        host_player = next((p for p in players if p.user_id == gs.host_user_id), players[0] if players else None)
        actor_user_id = host_player.user_id if host_player else gs.host_user_id
        actor_character_id = host_player.character_id if host_player else None

        ctx = ToolContext(db, gs, actor_user_id, actor_character_id)
        context = {
            "purpose": "session_opening",
            "player_action": (
                "SYSTEM:SESSION_OPENING — The session just started. "
                "Speak to the table in two short beats only: "
                "(1) a brief campaign overview grounded in campaign_overview, "
                "(2) the starting hook from campaign_start_hook as the live situation. "
                "Keep it concise (roughly 120–220 words total). "
                "Do not invent a different premise. Do not decide any PC's voluntary actions. "
                "Use update_world_state to set scene and location from the start hook."
            ),
            "actor_user_id": actor_user_id,
            "actor_character_id": actor_character_id,
            "character_name": "the table",
            "party": party,
            "campaign_state": ctx.state,
            "blueprint": blueprint,
            "opening_brief": opening_brief,
            "session_status": gs.status,
            "book_id": campaign.book_id if campaign else None,
            "rules_excerpts": [],
            "memories_gm": [],
            "memories_player": [],
        }

        turn = llm.complete_turn(context)
        for call in validate_tool_calls(turn.tool_calls or []):
            execute_tool(ctx, call["name"], call.get("args") or {})

        narration = (turn.narration or "").strip()
        # Opening should be a real cold open, not a meta "I'll set the scene".
        needs_narration = (
            not narration
            or len(narration) < 80
            or narration.lower().startswith(("i'll ", "i will ", "let me ", "okay"))
        )
        if (needs_narration or ctx.tool_results) and hasattr(llm, "narrate_after_tools"):
            follow = llm.narrate_after_tools(
                {**context, "pending_narration": turn.narration},
                ctx.tool_results,
            )
            if follow and len(follow.strip()) > len(narration):
                narration = follow.strip()
        if not narration:
            title = opening_brief["title"]
            overview = opening_brief["overview"]
            start_hook = opening_brief["start_hook"]
            narration = (
                f"Campaign brief — {title}. {overview} "
                f"Opening situation: {start_hook} "
                "What do you do?"
            )
            if not ctx.state.get("scene"):
                execute_tool(
                    ctx,
                    "update_world_state",
                    {
                        "patch": {
                            "scene": "Session opening",
                            "location": ctx.state.get("location") or "the starting place",
                            "notes": [overview[:160], start_hook[:160]],
                        }
                    },
                )

        observability = getattr(llm, "last_observability", None) or {
            "purpose": "session_opening",
            "provider": type(llm).__name__,
            "model": None,
            "latency_ms": None,
        }
        observability = {**observability, "request_id": request_id, "purpose": "session_opening"}

        ctx.append_event(
            "gm_narration",
            {
                "text": narration,
                "player_action": "SYSTEM:SESSION_OPENING",
                "kind": "session_opening",
                "observability": {
                    k: observability.get(k)
                    for k in (
                        "purpose",
                        "provider",
                        "model",
                        "latency_ms",
                        "prompt_tokens",
                        "completion_tokens",
                        "request_id",
                    )
                },
            },
        )
        ctx.persist_state(bump_version=True)
        envelopes = [event_to_envelope(ev) for ev in ctx._pending_publish]
        db.commit()
        for envelope in envelopes:
            hub_module.default_hub.publish(session_id, envelope)

        audio_dict = None
        try:
            from services.play.gm.voice_out import gm_audio_envelope, synthesize_table_audio

            speaker = getattr(turn, "speaker", None) or getattr(llm, "last_speaker", None) or "gm"
            voice_direction = getattr(turn, "voice_direction", None)
            if getattr(llm, "last_voice_direction", None) is not None:
                voice_direction = llm.last_voice_direction
            audio_dict = synthesize_table_audio(
                text=narration,
                speaker=speaker,
                voice_direction=voice_direction,
                tts=None,
            )
            if audio_dict:
                audio_dict["speaker"] = speaker
                hub_module.default_hub.publish(
                    session_id,
                    gm_audio_envelope(
                        session_id=session_id,
                        actor_id=actor_user_id,
                        audio_dict=audio_dict,
                        extra_payload={"kind": "session_opening"},
                    ),
                )
        except Exception:
            audio_dict = None

        logger.info(
            "gm_opening request_id=%s session_id=%s provider=%s",
            request_id,
            session_id,
            observability.get("provider"),
        )
        db.refresh(gs)
        return {
            "narration": narration,
            "state": load_state(gs.state_json),
            "state_version": gs.state_version,
            "events": ctx.events_out,
            "observability": observability,
            "audio": audio_dict,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
