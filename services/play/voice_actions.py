"""Voice action intake — STT then same FIFO GameMasterRuntime path as text."""

from __future__ import annotations

from typing import Any

from services.play.gm.actions import submit_player_action
from services.play.gm.errors import ActionError
from services.play.gm.tools import DiceRng
from services.rate_limit import check_play_voice_rate
from services.voice import SpeechToTextProvider, TextToSpeechProvider, resolve_stt


def submit_voice_action(
    user_id: str,
    session_id: str,
    audio: bytes,
    content_type: str = "audio/webm",
    *,
    stt: SpeechToTextProvider | None = None,
    tts: TextToSpeechProvider | None = None,
    llm: Any | None = None,
    dice_rng: DiceRng | None = None,
    speak: bool = True,
) -> dict:
    """Transcribe audio then enqueue as a normal player action.

    Player identity comes from ``user_id`` (authenticated connection), never from
    transcript content.
    """
    if not audio:
        raise ActionError("invalid", "Audio payload is required")

    if not check_play_voice_rate(user_id):
        raise ActionError("rate_limited", "Too many voice actions; slow down a moment")

    stt_provider = stt or resolve_stt()
    try:
        transcript = (stt_provider.transcribe(audio, content_type=content_type) or "").strip()
    except Exception as exc:  # noqa: BLE001
        raise ActionError("stt_failed", f"Speech recognition failed: {exc}") from exc
    if not transcript:
        raise ActionError("invalid", "Empty transcript from STT")

    result = submit_player_action(
        user_id,
        session_id,
        transcript,
        llm=llm,
        dice_rng=dice_rng,
        tts=tts if speak else None,
        speak=speak,
    )
    result["transcript"] = transcript
    result["actor_user_id"] = user_id
    result["input_modality"] = "voice"
    return result
