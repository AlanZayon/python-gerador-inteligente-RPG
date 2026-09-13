"""Text-to-Dialogue abstractions. Not used for simple GM narration.

Official future endpoint: POST /v1/text-to-dialogue (SDK ``text_to_dialogue.convert``).
Realtime TTD WebSocket is a separate product from HTTP TTS convert(); do not invent payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from services.voice.models import AudioResult


@dataclass
class DialogueTurn:
    text: str
    voice_id: str


@dataclass
class DialogueRequest:
    turns: list[DialogueTurn]


class TextToDialogueProvider(Protocol):
    def synthesize_dialogue(self, request: DialogueRequest) -> AudioResult: ...


class UnimplementedTextToDialogue:
    """Placeholder — multi-speaker dialogue is out of the TTS MVP."""

    def synthesize_dialogue(self, request: DialogueRequest) -> AudioResult:
        raise NotImplementedError(
            "Text-to-Dialogue is not implemented. Use ElevenLabs TTS convert() for "
            "single-speaker narration, or wire text_to_dialogue.convert later."
        )
