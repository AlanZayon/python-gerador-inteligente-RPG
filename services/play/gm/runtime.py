"""GameMasterRuntime — one exclusive flight per call site (caller holds lock)."""

from __future__ import annotations

import json
from typing import Any

from database import SessionLocal
from models.entities import Campaign, CampaignCharacter, GameSession, SessionPlayer
from services.play.gm.errors import ActionError
from services.play.gm.mock_llm import MockGMLLM
from services.play.gm.state import load_state
from services.play.gm.tools import DiceRng, ToolContext, execute_tool


def run_gm_flight(
    session_id: str,
    user_id: str,
    character_id: str,
    player_action: str,
    llm: Any | None = None,
    dice_rng: DiceRng | None = None,
) -> dict:
    llm = llm or MockGMLLM()
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
        context = {
            "player_action": player_action,
            "actor_user_id": user_id,
            "actor_character_id": character_id,
            "character_name": character.display_name if character else "",
            "role": membership.role if membership else "player",
            "campaign_state": ctx.state,
            "blueprint": blueprint,
            "session_status": gs.status,
        }
        turn = llm.complete_turn(context)
        for call in turn.tool_calls:
            execute_tool(ctx, call["name"], call.get("args") or {})

        narration = turn.narration
        if not narration and hasattr(llm, "narrate_after_tools"):
            narration = llm.narrate_after_tools(
                {**context, "pending_narration": turn.narration},
                ctx.tool_results,
            )
        if not narration:
            narration = "The moment hangs in the air."

        ctx.append_event(
            "gm_narration",
            {"text": narration, "player_action": player_action},
        )
        ctx.persist_state(bump_version=True)

        db.commit()
        db.refresh(gs)
        return {
            "narration": narration,
            "state": load_state(gs.state_json),
            "state_version": gs.state_version,
            "events": ctx.events_out,
            "tool_results": ctx.tool_results,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
