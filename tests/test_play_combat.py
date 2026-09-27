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
from services.play.gm.combat import (
    combat_policy_for_turn,
    current_combatant,
    looks_like_attack_or_damage_roll,
    looks_like_hostile_violence,
    looks_like_initiative_roll,
    ordered_combatants,
)
from services.play.gm.live_llm import LiveGMLLM
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


@pytest.mark.parametrize(
    "text",
    [
        "I attack the dwarf",
        "I swing at the bandit",
        "Ataco o guarda anão com minha espada",
        "Dou um golpe no guarda",
        "Atiro uma flecha contra o orc",
    ],
)
def test_hostile_violence_detected(text):
    assert looks_like_hostile_violence(text)


@pytest.mark.parametrize(
    "text",
    [
        "I hit the door",
        "Chuto a porta",
        "Treino com o boneco",
        "Me rendo aos guardas",
        "Não ataco o guarda",
        "Converso com o anão sobre a sociedade",
        "Pego uma flecha da aljava",
        "Entro na mata",
    ],
)
def test_non_combat_actions_not_flagged(text):
    assert not looks_like_hostile_violence(text)


def test_roll_classification():
    assert looks_like_attack_or_damage_roll("Força (Ataque com Arma)")
    assert looks_like_attack_or_damage_roll("Damage", "longsword")
    assert not looks_like_attack_or_damage_roll("Destreza (Iniciativa)")
    assert looks_like_initiative_roll("Initiative")
    assert not looks_like_attack_or_damage_roll("Força (Atletismo)", "escalar o muro")


def test_combat_policy_only_when_combat_inactive():
    policy = combat_policy_for_turn(
        purpose="gm_turn", player_action="I attack the dwarf", state={"combat": None}
    )
    assert policy and policy["hostile_violence_detected"]
    assert policy["required_order"][:2] == ["lookup_rules", "begin_combat"]
    active = {"combat": {"status": "active", "combatants": []}}
    assert combat_policy_for_turn(
        purpose="gm_turn", player_action="I attack the dwarf", state=active
    ) is None
    assert combat_policy_for_turn(
        purpose="gm_turn", player_action="I look around", state={"combat": None}
    ) is None
    resolved = combat_policy_for_turn(
        purpose="roll_resolution",
        player_action="",
        state={"combat": None},
        resolved_roll={"skill": "Força (Ataque com Arma)"},
    )
    assert resolved and resolved["attack_resolved_outside_combat"]


def test_live_prompt_includes_combat_policy():
    llm = LiveGMLLM(chat_fn=lambda **_: {})
    policy = {"combat_active": False, "hostile_violence_detected": True}
    messages = llm._build_messages(
        {"purpose": "gm_turn", "player_action": "I attack", "combat_policy": policy}
    )
    user = json.loads(messages[1]["content"])
    assert user["combat_policy"] == policy
    assert "initiative first" in messages[0]["content"].lower()
    assert "combat_policy" not in json.loads(
        llm._build_messages({"purpose": "gm_turn", "player_action": "I look"})[1]["content"]
    )


class _AttackFirstLLM:
    """Issues an attack Roll Call without opening combat (the bug we gate)."""

    def __init__(self):
        self.contexts: list[dict] = []

    def complete_turn(self, context: dict) -> LLMTurn:
        self.contexts.append(context)
        return LLMTurn(
            tool_calls=[
                {
                    "name": "request_roll",
                    "args": {
                        "skill": "Força (Ataque com Arma)",
                        "notation": "1d20+5",
                        "dc": 14,
                        "reason": "golpear o guarda anão",
                    },
                }
            ],
            narration="Você avança contra o guarda.",
        )

    def narrate_after_tools(self, context: dict, tool_results: list[dict]) -> str:
        return "A violência explode no portão — iniciativa!"


def test_attack_roll_without_combat_is_rejected(live_table):
    llm = _AttackFirstLLM()
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "Ataco o guarda anão",
        llm=llm,
    )
    gate = next(t for t in result["tool_results"] if t["name"] == "request_roll")
    assert gate["result"]["error"] == "combat_required"
    assert result["state"]["pending_check"] is None
    assert result["narration"] == "A violência explode no portão — iniciativa!"
    assert llm.contexts[0]["combat_policy"]["hostile_violence_detected"] is True


def test_initiative_roll_allowed_without_combat(live_table):
    class _InitLLM(_AttackFirstLLM):
        def complete_turn(self, context):
            return LLMTurn(
                tool_calls=[
                    {
                        "name": "request_roll",
                        "args": {"skill": "Iniciativa", "notation": "1d20+2", "reason": "luta"},
                    }
                ],
                narration="Mira, role iniciativa, 1d20+2.",
            )

    result = submit_player_action(
        live_table["host"].id, live_table["session_id"], "I draw steel", llm=_InitLLM()
    )
    assert result["state"]["pending_check"]["skill"] == "Iniciativa"


def test_attack_before_own_initiative_is_rejected(live_table):
    submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "GM_SCRIPT:begin_combat",
        llm=MockGMLLM(),
        retrieve_fn=_combat_retrieve,
    )
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "Ataco o bandido",
        llm=_AttackFirstLLM(),
    )
    gate = next(t for t in result["tool_results"] if t["name"] == "request_roll")
    assert gate["result"]["error"] == "initiative_required"
    assert result["state"]["pending_check"] is None


class _RecoveringLLM:
    """Attacks first, then follows the gate: lookup+begin_combat, then initiative."""

    def __init__(self):
        self.rounds = 0

    def complete_turn(self, context: dict) -> LLMTurn:
        return _AttackFirstLLM().complete_turn(context)

    def continue_with_tools(self, context: dict, tool_results: list[dict]) -> LLMTurn:
        self.rounds += 1
        if self.rounds == 1:
            assert any(
                (t.get("result") or {}).get("error") == "combat_required" for t in tool_results
            )
            return LLMTurn(
                tool_calls=[
                    {"name": "lookup_rules", "args": {"query": "initiative attack damage"}},
                    {
                        "name": "begin_combat",
                        "args": {"npcs": [{"name": "Guarda Anão", "hp": 11, "max_hp": 11}]},
                    },
                    {"name": "request_roll", "args": {"skill": "Força (Ataque)"}},
                ],
                narration="",
            )
        return LLMTurn(
            tool_calls=[
                {
                    "name": "request_roll",
                    "args": {"skill": "Iniciativa", "notation": "1d20+2", "reason": "combate"},
                }
            ],
            narration="O guarda saca o machado. Mira, role iniciativa, 1d20+2.",
        )

    def narrate_after_tools(self, context: dict, tool_results: list[dict]) -> str:
        return "O guarda saca o machado. Mira, role iniciativa, 1d20+2."


def test_gate_feeds_back_and_model_opens_combat(live_table):
    llm = _RecoveringLLM()
    result = submit_player_action(
        live_table["host"].id,
        live_table["session_id"],
        "Ataco o guarda anão",
        llm=llm,
        retrieve_fn=_combat_retrieve,
    )
    combat = result["state"]["combat"]
    assert combat and combat["status"] == "active"
    assert any(c["name"] == "Guarda Anão" for c in combat["combatants"])
    # begin_combat ran alongside lookup_rules; the bundled attack was deferred
    names = [t["name"] for t in result["tool_results"]]
    assert names.count("begin_combat") == 1
    assert result["state"]["pending_check"]["skill"] == "Iniciativa"
