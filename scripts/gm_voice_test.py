#!/usr/bin/env python
"""Manual GM voice test — real ElevenLabs convert() (not run in CI).

Usage (from repo root, with .env):

    python scripts/gm_voice_test.py
    python scripts/gm_voice_test.py --text "A porta começa a se abrir lentamente..." --speaker gm
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from services.voice.director import build_voice_director  # noqa: E402
from services.voice.models import Narration, VoiceDirection  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthesize a GM narration via VoiceDirector")
    parser.add_argument(
        "--text",
        default="A porta começa a se abrir lentamente...",
        help="Spoken text",
    )
    parser.add_argument("--speaker", default="gm", help="Speaker key (gm, villain, …)")
    parser.add_argument(
        "--out",
        default=str(ROOT / ".scratch" / "gm-voice-test.mp3"),
        help="Output audio path",
    )
    args = parser.parse_args()

    os.environ["VOICE_TTS_PROVIDER"] = "elevenlabs"

    director = build_voice_director()
    narration = Narration(
        speaker=args.speaker,
        text=args.text,
        voice_direction=VoiceDirection(tags=["[slowly]"]),
    )
    result = director.render(narration)
    if result is None:
        print("audio generation skipped (empty text or character limit)")
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(result.audio)
    print("audio generated successfully")
    print(f"provider: {result.provider}")
    print(f"voice: {args.speaker}")
    print(f"voice_id: {result.voice_id}")
    print(f"model: {result.model_id}")
    print(f"bytes: {len(result.audio)}")
    print(f"wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
