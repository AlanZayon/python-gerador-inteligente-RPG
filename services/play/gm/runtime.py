"""GameMasterRuntime — one exclusive flight per call site (caller holds lock)."""

from __future__ import annotations

import json
from typing import Any

from database import SessionLocal
from models.entities import Campaign, CampaignCharacter, GameSession, SessionPlayer
from services.play import hub as hub_module
from services.play.events import event_to_envelope
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


def run_gm_flight(
    session_id: str,
    user_id: str,
    character_id: str,
    player_action: str,
    llm: Any | None = None,
    dice_rng: DiceRng | None = None,
    retrieve_fn=None,
) -> dict:
    llm = llm or resolve_gm_llm()
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
        turn = llm.complete_turn(context)
        for call in validate_tool_calls(turn.tool_calls or []):
            execute_tool(ctx, call["name"], call.get("args") or {})

        narration = turn.narration
        if not narration and hasattr(llm, "narrate_after_tools"):
            narration = llm.narrate_after_tools(
                {**context, "pending_narration": turn.narration},
                ctx.tool_results,
            )
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

        observability = getattr(llm, "last_observability", None) or {
            "purpose": "gm_turn",
            "provider": type(llm).__name__,
            "model": None,
            "latency_ms": None,
        }

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
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
