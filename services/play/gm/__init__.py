"""Game Master Runtime — text turns with injectable LLM."""

from services.play.gm.actions import confirm_roll, submit_player_action
from services.play.gm.errors import ActionError
from services.play.gm.live_llm import LiveGMLLM
from services.play.gm.mock_llm import MockGMLLM
from services.play.gm.provider import resolve_gm_llm

__all__ = [
    "ActionError",
    "LiveGMLLM",
    "MockGMLLM",
    "confirm_roll",
    "resolve_gm_llm",
    "submit_player_action",
]
