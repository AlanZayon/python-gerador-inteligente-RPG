"""GameMasterRuntime — one exclusive flight per call site (caller holds lock)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from database import SessionLocal
from models.entities import Campaign, CampaignCharacter, GameSession, Job, SessionPlayer
from services.play import hub as hub_module
from services.play.events import event_to_envelope
from services.play.gm.agency import scrub_unsolicited_pc_actions
from services.play.gm.errors import ActionError
from services.play.gm.live_llm import MAX_TOOL_ROUNDS, validate_tool_calls
from services.play.gm.provider import resolve_gm_llm
from services.play.gm.rag_context import retrieve_gm_rules
from services.play.gm.roll_call_speech import ensure_spoken_roll_call, has_wait_meta
from services.play.gm.state import load_state
from services.play.gm.tools import DiceRng, ToolContext, execute_tool, resolve_roll_call
from services.play.memory import (
    filter_memories_for_character,
    list_memories_for_gm,
    scrub_table_narration,
)

logger = logging.getLogger(__name__)

LOOKUP_TOOLS = {"lookup_rules"}
IMMEDIATE_PC_DICE = {"roll_dice", "perform_check"}


def _needs_table_narration(text: str, has_tools: bool) -> bool:
    """True when the model returned planning fluff instead of table narration."""
    raw = (text or "").strip()
    if not raw:
        return True
    if has_wait_meta(raw):
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


def _sheet_brief(character: CampaignCharacter | None) -> dict:
    if not character:
        return {}
    try:
        sheet = json.loads(character.sheet_json or "{}")
    except json.JSONDecodeError:
        sheet = {}
    if not isinstance(sheet, dict):
        sheet = {}
    return {
        "name": sheet.get("name") or character.display_name,
        "class": sheet.get("class") or "",
        "level": sheet.get("level") or "",
        "abilities": str(sheet.get("abilities") or "")[:400],
        "raw_excerpt": str(sheet.get("raw_excerpt") or "")[:500],
    }


def _run_one_tool(ctx: ToolContext, call: dict, request_id: str, session_id: str) -> dict:
    tool_name = call["name"]
    try:
        tool_out = execute_tool(ctx, call["name"], call.get("args") or {})
    except Exception as exc:  # noqa: BLE001
        logger.exception("gm_tool_failed tool=%s session_id=%s", tool_name, session_id)
        tool_out = {"ok": False, "error": str(exc)[:200]}
        ctx.tool_results.append(
            {"name": tool_name, "args": call.get("args") or {}, "result": tool_out}
        )
    if ctx.tool_results:
        ctx.tool_results[-1]["id"] = call.get("id")
    logger.info(
        "gm_tool request_id=%s session_id=%s tool=%s ok=%s",
        request_id,
        session_id,
        tool_name,
        bool((tool_out or {}).get("ok")),
    )
    return tool_out


def _run_tool_loop(
    llm: Any,
    ctx: ToolContext,
    context: dict,
    turn,
    request_id: str,
    session_id: str,
):
    for round_i in range(MAX_TOOL_ROUNDS):
        calls = validate_tool_calls(turn.tool_calls or [])
        if not calls:
            break
        lookups = [c for c in calls if c["name"] in LOOKUP_TOOLS]
        others = [c for c in calls if c["name"] not in LOOKUP_TOOLS]
        can_continue = lookups and round_i < MAX_TOOL_ROUNDS - 1 and hasattr(llm, "continue_with_tools")
        if can_continue:
            lookup_results = []
            for call in lookups:
                _run_one_tool(ctx, call, request_id, session_id)
                lookup_results.append(ctx.tool_results[-1])
            try:
                turn = llm.continue_with_tools(context, lookup_results)
            except Exception:
                logger.exception("gm_continue_with_tools_failed session_id=%s", session_id)
                break
            continue
        if context.get("purpose") == "roll_resolution":
            others = [c for c in others if c["name"] != "request_roll"]
        if any(c["name"] == "request_roll" for c in others):
            others = [c for c in others if c["name"] not in IMMEDIATE_PC_DICE]
        for call in lookups + others:
            _run_one_tool(ctx, call, request_id, session_id)
        break
    return turn


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
    purpose: str = "gm_turn",
    pending_id: str | None = None,
    chosen_skill: str | None = None,
    chosen_index: int | None = None,
) -> dict:
    llm = llm or resolve_gm_llm()
    purpose = purpose or "gm_turn"
    request_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        gs = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not gs:
            raise ActionError("not_found", "GameSession not found")
        campaign = db.query(Campaign).filter(Campaign.id == gs.campaign_id).first()
        job = None
        if campaign:
            job = db.query(Job).filter(Job.id == campaign.job_id).first()
        system_preset = (job.system_preset if job else None) or "generic"
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

        ctx = ToolContext(
            db,
            gs,
            user_id,
            character_id,
            dice_rng=dice_rng,
            book_id=campaign.book_id if campaign else None,
            retrieve_fn=retrieve_fn,
            purpose=purpose,
        )
        state = ctx.state
        resolved_roll = None
        if purpose == "roll_resolution":
            resolved = resolve_roll_call(
                ctx,
                pending_id,
                chosen_skill=chosen_skill,
                chosen_index=chosen_index,
            )
            if not resolved.get("ok"):
                if resolved.get("error") == "needs_choice":
                    raise ActionError("needs_choice", "Choose which check to roll.")
                raise ActionError("not_ready", resolved.get("error") or "No Roll Call is waiting")
            resolved_roll = resolved.get("result")
            state = ctx.state

        rules_excerpts = retrieve_gm_rules(
            book_id=campaign.book_id if campaign else None,
            player_action=player_action,
            scene=state.get("scene") or gs.current_scene or "",
            location=state.get("location") or "",
            character_name=character.display_name if character else "",
            system_preset=system_preset,
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
            "purpose": purpose,
            "player_action": player_action,
            "actor_user_id": user_id,
            "actor_character_id": character_id,
            "character_name": character.display_name if character else "",
            "actor_sheet": _sheet_brief(character),
            "system_preset": system_preset,
            "role": membership.role if membership else "player",
            "campaign_state": state,
            "blueprint": blueprint,
            "session_status": gs.status,
            "book_id": campaign.book_id if campaign else None,
            "rules_excerpts": rules_excerpts,
            "resolved_roll": resolved_roll,
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
        turn = _run_tool_loop(llm, ctx, context, turn, request_id, session_id)

        narration = (turn.narration or "").strip()
        speaker = getattr(turn, "speaker", None) or "gm"
        voice_direction = getattr(turn, "voice_direction", None)
        if _needs_table_narration(narration, bool(ctx.tool_results)) and hasattr(
            llm, "narrate_after_tools"
        ):
            follow = llm.narrate_after_tools(
                {**context, "pending_narration": turn.narration, "campaign_state": ctx.state},
                ctx.tool_results,
            )
            if follow and (
                has_wait_meta(narration) or len(follow.strip()) >= len(narration)
            ):
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
        pending = ctx.state.get("pending_check") if isinstance(ctx.state, dict) else None
        if isinstance(pending, dict) and pending:
            job_lang = (job.language if job else None) or "en"
            table_narration = ensure_spoken_roll_call(
                table_narration,
                pending,
                character_name=character.display_name if character else "",
                language=job_lang,
            )

        observability = getattr(llm, "last_observability", None) or {
            "purpose": purpose,
            "provider": type(llm).__name__,
            "model": None,
            "latency_ms": None,
        }
        observability = {**observability, "request_id": request_id, "purpose": purpose}

        logger.info(
            "gm_turn request_id=%s session_id=%s actor_user_id=%s provider=%s model=%s "
            "latency_ms=%s tools=%s purpose=%s",
            request_id,
            session_id,
            user_id,
            observability.get("provider"),
            observability.get("model"),
            observability.get("latency_ms"),
            len(ctx.tool_results),
            purpose,
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
