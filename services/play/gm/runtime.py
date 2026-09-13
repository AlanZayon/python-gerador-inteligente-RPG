"""GameMasterRuntime — one exclusive flight per call site (caller holds lock)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from database import SessionLocal
from models.entities import Campaign, CampaignCharacter, GameSession, SessionPlayer
from services.play import hub as hub_module
from services.play.events import event_to_envelope
from services.play.gm.agency import scrub_unsolicited_pc_actions
from services.play.gm.errors import ActionError
from services.play.gm.live_llm import validate_tool_calls
from services.play.gm.provider import resolve_gm_llm
from services.play.gm.rag_context import retrieve_gm_rules
from services.play.gm.state import load_state
from services.play.gm.tools import DiceRng, ToolContext, execute_tool
from services.play.memory import (
    filter_memories_for_character,
    list_memories_for_gm,
    scrub_table_narration,
)

logger = logging.getLogger(__name__)


def _needs_table_narration(text: str, has_tools: bool) -> bool:
    """True when the model returned planning fluff instead of table narration."""
    raw = (text or "").strip()
    if not raw:
        return True
    if has_tools and len(raw) < 80:
        return True
    lower = raw.lower()
    meta_prefixes = (
        "i'll ",
        "i will ",
        "let me ",
        "okay",
        "i am ",
        "i'm ",
        "i'm reading",
        "i am reading",
        "reading the campaign",
        "preparing the scene",
        "checking the",
        "looking at the state",
    )
    return any(lower.startswith(p) or p in lower[:80] for p in meta_prefixes)


def run_gm_flight(
    session_id: str,
    user_id: str,
    character_id: str,
    player_action: str,
    llm: Any | None = None,
    dice_rng: DiceRng | None = None,
    retrieve_fn=None,
    tts: Any | None = None,
    speak: bool = True,
) -> dict:
    llm = llm or resolve_gm_llm()
    request_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        gs = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not gs:
            raise ActionError("not_found", "GameSession not found")
        campaign = db.query(Campaign).filter(Campaign.id == gs.campaign_id).first()
        membership = (
            db.query(SessionPlayer)
            .filter(SessionPlayer.game_session_id == session_id, SessionPlayer.user_id == user_id)
            .first()
        )
        character = (
            db.query(CampaignCharacter)
            .filter(CampaignCharacter.id == character_id)
            .first()
        )
        seated = (
            db.query(SessionPlayer)
            .filter(SessionPlayer.game_session_id == session_id)
            .all()
        )
        other_names = []
        for sp in seated:
            if not sp.character_id or sp.character_id == character_id:
                continue
            other = (
                db.query(CampaignCharacter)
                .filter(CampaignCharacter.id == sp.character_id)
                .first()
            )
            if other and other.display_name:
                other_names.append(other.display_name)
        blueprint = {}
        if campaign and campaign.blueprint_json:
            try:
                blueprint = json.loads(campaign.blueprint_json)
            except json.JSONDecodeError:
                blueprint = {}

        ctx = ToolContext(db, gs, user_id, character_id, dice_rng=dice_rng)
        state = ctx.state
        rules_excerpts = retrieve_gm_rules(
            book_id=campaign.book_id if campaign else None,
            player_action=player_action,
            scene=state.get("scene") or gs.current_scene or "",
            location=state.get("location") or "",
            character_name=character.display_name if character else "",
            retrieve_fn=retrieve_fn,
        )
        memories_gm = list_memories_for_gm(
            campaign_id=gs.campaign_id,
            game_session_id=session_id,
            db=db,
        )
        memories_player = filter_memories_for_character(
            campaign_id=gs.campaign_id,
            game_session_id=session_id,
            character_id=character_id,
            db=db,
        )
        context = {
            "player_action": player_action,
            "actor_user_id": user_id,
            "actor_character_id": character_id,
            "character_name": character.display_name if character else "",
            "role": membership.role if membership else "player",
            "campaign_state": state,
            "blueprint": blueprint,
            "session_status": gs.status,
            "book_id": campaign.book_id if campaign else None,
            "rules_excerpts": rules_excerpts,
            # GM continuity: all scopes including others' private knowledge
            "memories_gm": memories_gm,
            # Player-facing filtered layer (no other Characters' private knowledge)
            "memories_player": memories_player,
        }
        try:
            turn = llm.complete_turn(context)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "gm_llm_failed request_id=%s session_id=%s err=%s",
                request_id,
                session_id,
                exc,
            )
            from services.play.gm.mock_llm import LLMTurn

            turn = LLMTurn(
                tool_calls=[],
                narration=(
                    "The weave flickers and the Game Master loses the thread for a moment. "
                    "Describe your action again when you are ready."
                ),
            )
        for call in validate_tool_calls(turn.tool_calls or []):
            tool_name = call["name"]
            try:
                tool_out = execute_tool(ctx, call["name"], call.get("args") or {})
            except Exception as exc:  # noqa: BLE001
                logger.exception("gm_tool_failed tool=%s session_id=%s", tool_name, session_id)
                tool_out = {"ok": False, "error": str(exc)[:200]}
                ctx.tool_results.append(
                    {"name": tool_name, "args": call.get("args") or {}, "result": tool_out}
                )
            logger.info(
                "gm_tool request_id=%s session_id=%s tool=%s ok=%s",
                request_id,
                session_id,
                tool_name,
                bool((tool_out or {}).get("ok")),
            )

        narration = (turn.narration or "").strip()
        speaker = getattr(turn, "speaker", None) or "gm"
        voice_direction = getattr(turn, "voice_direction", None)
        if _needs_table_narration(narration, bool(ctx.tool_results)) and hasattr(
            llm, "narrate_after_tools"
        ):
            follow = llm.narrate_after_tools(
                {**context, "pending_narration": turn.narration},
                ctx.tool_results,
            )
            if follow and len(follow.strip()) >= len(narration):
                narration = follow.strip()
                if getattr(llm, "last_speaker", None):
                    speaker = llm.last_speaker
                if getattr(llm, "last_voice_direction", None) is not None:
                    voice_direction = llm.last_voice_direction
        if not narration:
            narration = "The moment hangs in the air."

        # Refresh private set after tools may have written new secrets this turn
        memories_gm_after = list_memories_for_gm(
            campaign_id=gs.campaign_id,
            game_session_id=session_id,
            db=db,
        )
        private_all = [m for m in memories_gm_after if m.get("scope") == "character_private"]
        # Table-wide narration must not auto-reveal character-private knowledge
        table_narration = scrub_table_narration(narration, private_all)
        table_narration = scrub_unsolicited_pc_actions(
            table_narration,
            actor_name=character.display_name if character else None,
            other_names=other_names,
            player_action=player_action,
        )

        observability = getattr(llm, "last_observability", None) or {
            "purpose": "gm_turn",
            "provider": type(llm).__name__,
            "model": None,
            "latency_ms": None,
        }
        observability = {**observability, "request_id": request_id}

        logger.info(
            "gm_turn request_id=%s session_id=%s actor_user_id=%s provider=%s model=%s "
            "latency_ms=%s tools=%s",
            request_id,
            session_id,
            user_id,
            observability.get("provider"),
            observability.get("model"),
            observability.get("latency_ms"),
            len(ctx.tool_results),
        )

        ctx.append_event(
            "gm_narration",
            {
                "text": table_narration,
                "player_action": player_action,
                "observability": {
                    k: observability.get(k)
                    for k in (
                        "purpose",
                        "provider",
                        "model",
                        "latency_ms",
                        "prompt_tokens",
                        "completion_tokens",
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
        if speak:
            try:
                from services.play.gm.voice_out import gm_audio_envelope, synthesize_table_audio

                audio_dict = synthesize_table_audio(
                    text=table_narration,
                    speaker=speaker,
                    voice_direction=voice_direction,
                    tts=tts,
                )
                if audio_dict:
                    if speaker:
                        audio_dict["speaker"] = speaker
                    hub_module.default_hub.publish(
                        session_id,
                        gm_audio_envelope(
                            session_id=session_id,
                            actor_id=user_id,
                            audio_dict=audio_dict,
                        ),
                    )
            except Exception:
                # Text-first: voice failure must not roll back Campaign State.
                audio_dict = None

        db.refresh(gs)
        return {
            "narration": table_narration,
            "state": load_state(gs.state_json),
            "state_version": gs.state_version,
            "events": ctx.events_out,
            "tool_results": ctx.tool_results,
            "rules_excerpts": rules_excerpts,
            "observability": observability,
            "memories_player": memories_player,
            "audio": audio_dict,
            "actor_user_id": user_id,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
