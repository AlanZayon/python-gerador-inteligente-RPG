"""Play Application: light Combat Encounter tracker."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models.entities import Campaign, CampaignCharacter, Job, User
from services.play.gm import ActionError, MockGMLLM, confirm_roll, submit_player_action
from services.play.gm.combat import current_combatant, ordered_combatants
from services.play.gm.mock_llm import LLMTurn
from services.play.gm.rag_context import build_gm_query
from services.play.gm.state import dump_state, load_state
from services.play.sessions import (
    claim_character,
    create_game_session,
    join_game_session,
    set_ready,
    start_game_session,
)
from services.play.sync import get_reconnect_snapshot


@pytest.fixture
def live_table(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr("services.play.sessions.SessionLocal", Session)
    monkeypatch.setattr("services.play.gm.runtime.SessionLocal", Session)
    monkeypatch.setattr("services.play.gm.actions.SessionLocal", Session)
    monkeypatch.setattr("services.play.sync.SessionLocal", Session)
    monkeypatch.setenv("VOICE_TTS_PROVIDER", "mock")
    monkeypatch.setenv("VOICE_STT_PROVIDER", "mock")

    import services.play.gm.actions as actions_mod

    actions_mod._locks.clear()
    actions_mod._queues.clear()

    db = Session()
    host = User(clerk_id="host", email="host@ex.com")
    p2 = User(clerk_id="p2", email="p2@ex.com")
    db.add_all([host, p2])
    db.commit()
    for u in (host, p2):
        db.refresh(u)

    job = Job(
        id="job-combat",
        user_id=host.id,
        status="completed",
        blueprint_json=json.dumps({"title": "Salt", "premise": "Storms gather."}),
        book_id="bk_combat",
        system_preset="generic",
        campaign_s3_key="c.md",
    )
    db.add(job)
    db.commit()
    campaign = Campaign(
        job_id=job.id,
        host_user_id=host.id,
        book_id="bk_combat",
        title="Salt",
        blueprint_json=job.blueprint_json,
        status="ready",
    )
    db.add(campaign)
    db.flush()
    chars = []
    for i, name in enumerate(["Mira", "Joren"]):
        c = CampaignCharacter(
            campaign_id=campaign.id,
            display_name=name,
            sheet_json=json.dumps(
                {"name": name, "class": "Rogue", "abilities": "DEX 16", "raw_excerpt": "Stealth +5"}
            ),
            sort_order=i,
            claimable=True,
        )
        db.add(c)
        chars.append(c)
    db.commit()
    for c in chars:
        db.refresh(c)

    gs = create_game_session(host.id, campaign.id)
    join_game_session(p2.id, gs.invite_code)
    claim_character(host.id, gs.id, chars[0].id)
    claim_character(p2.id, gs.id, chars[1].id)
    set_ready(host.id, gs.id, True)
    set_ready(p2.id, gs.id, True)
    start_game_session(host.id, gs.id)

    payload = {
        "Session": Session,
        "host": host,
        "p2": p2,
        "chars": chars,
        "session_id": gs.id,
        "campaign": campaign,
    }
    db.close()
    yield payload


def _combat_retrieve(*, book_id, query, top_k=None, **_):
    return [
        {
            "text": "Initiative: each combatant rolls; highest acts first. "
            "Attacks use a check against defense; damage reduces hit points.",
            "score": 0.95,
            "id": "cb1",
        }
    ]


def test_load_state_preserves_combat():
    raw = dump_state(
        {
            "scene": "Alley",
            "combat": {"id": "c1", "status": "active", "round": 1, "combatants": []},
        }
    )
    loaded = load_state(raw)
    assert loaded["combat"]["id"] == "c1"
    assert loaded["combat"]["status"] == "active"


def test_build_gm_query_biases_combat_actions():
    q = build_gm_query("I attack the bandit", system_preset="generic")
    assert "initiative" in q.lower() or "attack" in q.lower()
    assert "damage" in q.lower()


def test_begin_combat_creates_pcs_and_npcs(live_table):
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "GM_SCRIPT:begin_combat",
        llm=MockGMLLM(),
        retrieve_fn=_combat_retrieve,
    )
    combat = result["state"]["combat"]
    assert combat and combat["status"] == "active"
    names = {c["name"] for c in combat["combatants"]}
    assert "Mira" in names
    assert "Joren" in names
    assert "Bandit" in names
    bandit = next(c for c in combat["combatants"] if c["name"] == "Bandit")
    assert bandit["hp"] == 10
    assert bandit["kind"] == "npc"
    assert any(e["type"] == "combat_started" for e in result["events"])
    assert any(t["name"] == "lookup_rules" for t in result["tool_results"])
    assert any(t["name"] == "begin_combat" for t in result["tool_results"])
    lookup = next(t for t in result["tool_results"] if t["name"] == "lookup_rules")
    assert "initiative" in json.dumps(lookup["result"]).lower() or "Initiative" in json.dumps(
        lookup["result"]
    )


def test_initiative_orders_turns_and_gates_off_turn(live_table):
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "GM_SCRIPT:begin_combat",
        llm=MockGMLLM(),
        retrieve_fn=_combat_retrieve,
    )
    snap = get_reconnect_snapshot(live_table["host"].id, live_table["session_id"])
    combat = snap["state"]["combat"]
    mira = next(c for c in combat["combatants"] if c["name"] == "Mira")
    joren = next(c for c in combat["combatants"] if c["name"] == "Joren")
    bandit = next(c for c in combat["combatants"] if c["name"] == "Bandit")

    # Mira 15, Bandit 12, Joren 5 → Mira first
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        f"GM_SCRIPT:set_init {mira['id']} 15",
        llm=MockGMLLM(),
    )
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        f"GM_SCRIPT:set_init {bandit['id']} 12",
        llm=MockGMLLM(),
    )
    # Host is Mira — after setting bandit init, still Mira's turn so host can set Joren
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        f"GM_SCRIPT:set_init {joren['id']} 5",
        llm=MockGMLLM(),
    )

    snap = get_reconnect_snapshot(live_table["host"].id, live_table["session_id"])
    combat = snap["state"]["combat"]
    ordered = ordered_combatants(combat)
    assert [c["name"] for c in ordered[:3]] == ["Mira", "Bandit", "Joren"]
    current = current_combatant(combat)
    assert current["name"] == "Mira"

    with pytest.raises(ActionError) as exc:
        submit_player_action(
            live_table["p2"].id,
            live_table["session_id"],
            "I swing at the bandit",
            llm=MockGMLLM(),
        )
    assert exc.value.code == "not_your_turn"


def test_apply_harm_and_end_combat(live_table):
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "GM_SCRIPT:begin_combat",
        llm=MockGMLLM(),
        retrieve_fn=_combat_retrieve,
    )
    snap = get_reconnect_snapshot(live_table["host"].id, live_table["session_id"])
    bandit = next(c for c in snap["state"]["combat"]["combatants"] if c["name"] == "Bandit")
    mira = next(c for c in snap["state"]["combat"]["combatants"] if c["name"] == "Mira")
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        f"GM_SCRIPT:set_init {mira['id']} 20",
        llm=MockGMLLM(),
    )
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        f"GM_SCRIPT:set_init {bandit['id']} 1",
        llm=MockGMLLM(),
    )

    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        f"GM_SCRIPT:harm {bandit['id']} 4",
        llm=MockGMLLM(),
    )
    updated = next(c for c in result["state"]["combat"]["combatants"] if c["id"] == bandit["id"])
    assert updated["hp"] == 6
    assert "6" in result["narration"] or "Bandit" in result["narration"]
    assert any(e["type"] == "combatant_updated" for e in result["events"])

    ended = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "GM_SCRIPT:end_combat",
        llm=MockGMLLM(),
    )
    assert ended["state"]["combat"] is None
    assert any(e["type"] == "combat_ended" for e in ended["events"])

    # After combat, p2 can act again
    ok = submit_player_action(
        live_table["p2"].id,
        live_table["session_id"],
        "I look around",
        llm=MockGMLLM(),
    )
    assert ok["narration"]


class _AttackThenHarmLLM:
    """PC attack Roll Call, then on resolution apply_harm to Bandit."""

    def __init__(self, bandit_id: str):
        self.bandit_id = bandit_id

    def complete_turn(self, context: dict) -> LLMTurn:
        if context.get("purpose") == "roll_resolution":
            result = context.get("resolved_roll") or {}
            return LLMTurn(
                tool_calls=[
                    {
                        "name": "apply_harm",
                        "args": {
                            "combatant_id": self.bandit_id,
                            "amount": 3,
                            "summary": f"hit for {result.get('total')}",
                        },
                    },
                    {"name": "next_turn", "args": {"summary": "Mira strikes"}},
                ],
                narration="",
            )
        return LLMTurn(
            tool_calls=[
                {
                    "name": "request_roll",
                    "args": {
                        "skill": "Attack",
                        "notation": "1d20+4",
                        "dc": 12,
                        "reason": "Strike the bandit",
                    },
                }
            ],
            narration="Mira lunges.",
        )

    def narrate_after_tools(self, context: dict, tool_results: list[dict]) -> str:
        for tr in tool_results:
            if tr["name"] == "apply_harm" and tr["result"].get("ok"):
                c = tr["result"]["result"]
                return f"The attack lands. Bandit has {c.get('hp')} HP."
            if tr["name"] == "request_roll" and tr["result"].get("ok"):
                return "Mira, make an Attack check (1d20+4) against DC 12."
        return "The moment passes."


def test_pc_attack_roll_then_harm(live_table):
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "GM_SCRIPT:begin_combat",
        llm=MockGMLLM(),
        retrieve_fn=_combat_retrieve,
    )
    snap = get_reconnect_snapshot(live_table["host"].id, live_table["session_id"])
    bandit = next(c for c in snap["state"]["combat"]["combatants"] if c["name"] == "Bandit")
    mira = next(c for c in snap["state"]["combat"]["combatants"] if c["name"] == "Mira")
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        f"GM_SCRIPT:set_init {mira['id']} 20",
        llm=MockGMLLM(),
    )
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        f"GM_SCRIPT:set_init {bandit['id']} 1",
        llm=MockGMLLM(),
    )

    llm = _AttackThenHarmLLM(bandit["id"])
    called = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "I attack the bandit",
        llm=llm,
    )
    pending = called["state"]["pending_check"]
    assert pending and pending["skill"] == "Attack"

    result = confirm_roll(
        live_table["host"].id,
        live_table["session_id"],
        pending_id=pending["id"],
        llm=llm,
        dice_rng=lambda sides: 15,
    )
    assert result["state"]["pending_check"] is None
    updated = next(c for c in result["state"]["combat"]["combatants"] if c["id"] == bandit["id"])
    assert updated["hp"] == 7
    assert "7" in result["narration"] or "Bandit" in result["narration"]
    # Turn advanced to Bandit
    current = current_combatant(result["state"]["combat"])
    assert current["name"] == "Bandit"
