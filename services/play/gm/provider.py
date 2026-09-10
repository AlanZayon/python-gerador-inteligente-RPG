"""Select Game Master LLM provider (mock by default)."""

from __future__ import annotations

import os

from services.play.gm.live_llm import LiveGMLLM
from services.play.gm.mock_llm import MockGMLLM


def resolve_gm_llm():
    """Return mock unless GM_LLM_PROVIDER=9router and keys are configured."""
    provider = (os.getenv("GM_LLM_PROVIDER") or "mock").strip().lower()
    if provider in {"9router", "live", "ninerouter"}:
        from services.llm_client import is_configured

        if is_configured():
            model = (
                os.getenv("GM_LLM_MODEL")
                or os.getenv("LLM_MODEL_FLASH")
                or os.getenv("LLM_MODEL")
                or None
            )
            return LiveGMLLM(model=model)
    return MockGMLLM()
