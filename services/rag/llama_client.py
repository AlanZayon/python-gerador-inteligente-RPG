"""HTTP client for llama.cpp server (llama-server)."""

import logging

import requests

from services.rag.config import (
    LLAMA_BASE_URL,
    LLAMA_N_PREDICT,
    LLAMA_TEMPERATURE,
    LLAMA_TIMEOUT,
)

logger = logging.getLogger(__name__)


class LlamaServerError(Exception):
    pass


class LlamaServerUnavailable(LlamaServerError):
    pass


def complete(prompt: str) -> str:
    """
    Send prompt to llama-server /completion endpoint.

    TODO: streaming, retry with backoff, grammar/JSON mode.
    """
    url = f"{LLAMA_BASE_URL}/completion"
    payload = {
        "prompt": prompt,
        "n_predict": LLAMA_N_PREDICT,
        "temperature": LLAMA_TEMPERATURE,
        "stop": ["</s>", "<|eot_id|>"],
    }

    try:
        response = requests.post(url, json=payload, timeout=LLAMA_TIMEOUT)
    except requests.ConnectionError as exc:
        raise LlamaServerUnavailable(
            f"Cannot reach llama-server at {LLAMA_BASE_URL}. Is it running?"
        ) from exc
    except requests.Timeout as exc:
        raise LlamaServerError(f"llama-server timed out after {LLAMA_TIMEOUT}s") from exc

    if response.status_code >= 500:
        raise LlamaServerUnavailable(f"llama-server error {response.status_code}: {response.text[:200]}")

    if response.status_code != 200:
        raise LlamaServerError(f"llama-server returned {response.status_code}: {response.text[:200]}")

    data = response.json()
    content = data.get("content") or data.get("completion") or ""
    if not content.strip():
        raise LlamaServerError("llama-server returned empty content")
    return content.strip()


def health_check() -> bool:
    """Return True if llama-server responds."""
    try:
        r = requests.get(f"{LLAMA_BASE_URL}/health", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False
