"""HTTP client for local LLM inference via 9router (OpenAI-compatible)."""

from services.llm_client import (
    LLMError as LlamaServerError,
    LLMUnavailable as LlamaServerUnavailable,
    complete as _complete,
    health_check as _health_check,
)

__all__ = [
    "LlamaServerError",
    "LlamaServerUnavailable",
    "complete",
    "health_check",
]


def complete(prompt: str) -> str:
    return _complete(prompt)


def health_check() -> bool:
    return _health_check()
