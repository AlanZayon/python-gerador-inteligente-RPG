"""HTTP client for 9router (OpenAI-compatible /v1/chat/completions)."""

from __future__ import annotations

import json
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:20128"
_DEFAULT_MODEL = "my-combo"


class LLMError(Exception):
    """9router returned an unusable response."""


class LLMUnavailable(LLMError):
    """9router is unreachable or not configured."""


def _normalize_base_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    return url or _DEFAULT_BASE_URL


def _base_url() -> str:
    return _normalize_base_url(
        os.getenv("NINEROUTER_URL") or os.getenv("LLAMA_BASE_URL") or _DEFAULT_BASE_URL
    )


def _api_key() -> str:
    return (
        os.getenv("NINEROUTER_KEY")
        or os.getenv("NINEROUTER_API_KEY")
        or os.getenv("LLM_API_KEY")
        or ""
    ).strip()


def default_model() -> str:
    return (
        os.getenv("LLM_MODEL")
        or os.getenv("NINEROUTER_MODEL")
        or os.getenv("LLAMA_MODEL")
        or _DEFAULT_MODEL
    )


def model_lite() -> str:
    return os.getenv("LLM_MODEL_LITE") or default_model()


def model_flash() -> str:
    return os.getenv("LLM_MODEL_FLASH") or default_model()


def model_pro() -> str:
    return os.getenv("LLM_MODEL_PRO") or default_model()


def model_for_complexity(complexity: str) -> str:
    mapping = {
        "simples": model_lite(),
        "mediana": model_flash(),
        "complexa": model_pro(),
    }
    return mapping.get(complexity, model_flash())


def is_configured() -> bool:
    key = _api_key()
    return bool(key) and key not in {"sua_chave_aqui", "changeme"} and len(key) > 8


def is_gemini_configured() -> bool:
    """Backward-compatible alias — Gemini SDK is no longer used."""
    return is_configured()


def _timeout() -> int:
    return int(os.getenv("LLM_TIMEOUT") or os.getenv("LLAMA_TIMEOUT") or "600")


def _retry_attempts() -> int:
    return int(os.getenv("LLM_RETRY_ATTEMPTS") or os.getenv("GEMINI_RETRY_ATTEMPTS") or "3")


def _temperature() -> float:
    return float(os.getenv("LLM_TEMPERATURE") or os.getenv("LLAMA_TEMPERATURE") or "0.7")


def _max_tokens() -> int:
    return int(os.getenv("LLM_MAX_TOKENS") or os.getenv("LLAMA_N_PREDICT") or "8192")


def _extract_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise LLMError("Empty response from 9router")

    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message") or {}
    content = message.get("content")
    if content is None:
        content = choice.get("text")

    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
        content = "".join(parts)

    text = (content or "").strip() if isinstance(content, str) else str(content or "").strip()
    if not text:
        raise LLMError("Empty text from 9router")
    return text


def complete(
    prompt: str,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Send a single-turn prompt to 9router and return assistant text."""
    result = chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        purpose="complete",
    )
    text = ((result.get("message") or {}).get("content") or "").strip()
    if not text:
        raise LLMError("Empty text from 9router")
    return text


def chat_completion(
    *,
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    purpose: str = "chat",
) -> dict:
    """OpenAI-compatible chat completions with optional tool calling.

    Returns:
        {
          message, tool_calls: [{id,name,args}], usage, model, latency_ms, raw
        }
    """
    if not is_configured():
        raise LLMUnavailable("9router API key is not configured")

    url = f"{_base_url()}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    chosen_model = model or default_model()
    body: dict = {
        "model": chosen_model,
        "messages": messages,
        "stream": False,
        "temperature": _temperature() if temperature is None else temperature,
        "max_tokens": _max_tokens() if max_tokens is None else max_tokens,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    last_error: Exception | None = None
    attempts = max(1, _retry_attempts())
    started = time.perf_counter()
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(url, json=body, headers=headers, timeout=_timeout())
            if response.status_code in {401, 403}:
                raise LLMUnavailable("9router rejected the API key")
            if response.status_code == 503:
                raise LLMUnavailable(response.text[:500] or "9router has no available accounts")
            if response.status_code >= 400:
                raise LLMError(f"9router HTTP {response.status_code}: {response.text[:500]}")
            payload = response.json()
            latency_ms = (time.perf_counter() - started) * 1000.0
            message, tool_calls = _extract_message_and_tools(payload)
            usage = payload.get("usage") or {}
            logger.info(
                "llm_chat purpose=%s model=%s latency_ms=%.1f prompt_tokens=%s completion_tokens=%s",
                purpose,
                chosen_model,
                latency_ms,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
            return {
                "message": message,
                "tool_calls": tool_calls,
                "usage": usage,
                "model": chosen_model,
                "latency_ms": latency_ms,
                "purpose": purpose,
                "raw": payload,
            }
        except LLMUnavailable:
            raise
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                break
            wait = 2**attempt
            logger.warning("9router attempt %s failed: %s. Retrying in %ss...", attempt, exc, wait)
            time.sleep(wait)

    raise last_error or LLMError("9router request failed")


def _extract_message_and_tools(payload: dict) -> tuple[dict, list[dict]]:
    choices = payload.get("choices") or []
    if not choices:
        raise LLMError("Empty response from 9router")
    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message") or {}
    if not isinstance(message, dict):
        message = {"role": "assistant", "content": str(message)}

    content = message.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
        message = {**message, "content": "".join(parts)}

    tool_calls: list[dict] = []
    for tc in message.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        args_raw = fn.get("arguments")
        args: dict | str | None
        if isinstance(args_raw, dict):
            args = args_raw
        elif isinstance(args_raw, str):
            try:
                args = json.loads(args_raw) if args_raw.strip() else {}
            except json.JSONDecodeError:
                args = args_raw
        else:
            args = {}
        tool_calls.append(
            {
                "id": tc.get("id"),
                "name": fn.get("name") or tc.get("name") or "",
                "args": args,
            }
        )
    return message, tool_calls


def health_check() -> bool:
    try:
        response = requests.get(f"{_base_url()}/api/health", timeout=5)
        if response.ok and response.json().get("ok") is True:
            return True
    except Exception:
        logger.debug("9router /api/health failed", exc_info=True)

    try:
        headers = {}
        key = _api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        response = requests.get(f"{_base_url()}/v1/models", headers=headers, timeout=8)
        return response.ok
    except Exception:
        return False
