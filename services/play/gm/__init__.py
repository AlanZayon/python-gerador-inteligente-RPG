"""Game Master Runtime — text turns with injectable LLM."""

from services.play.gm.actions import submit_player_action
from services.play.gm.errors import ActionError
from services.play.gm.mock_llm import MockGMLLM

__all__ = ["ActionError", "MockGMLLM", "submit_player_action"]
