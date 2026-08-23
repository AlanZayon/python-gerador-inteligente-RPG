"""Unit tests for the 9router OpenAI-compatible client."""

from unittest.mock import MagicMock, patch

import pytest

from services import llm_client


def test_normalize_base_url_strips_v1():
    assert llm_client._normalize_base_url("http://localhost:20128/v1") == "http://localhost:20128"
    assert llm_client._normalize_base_url("http://localhost:20128/v1/") == "http://localhost:20128"
    assert llm_client._normalize_base_url("http://localhost:20128") == "http://localhost:20128"


def test_is_configured(monkeypatch):
    monkeypatch.setenv("NINEROUTER_KEY", "sk-test-abcdefghijklmnopqrstuv")
    assert llm_client.is_configured() is True

    monkeypatch.setenv("NINEROUTER_KEY", "short")
    assert llm_client.is_configured() is False

    monkeypatch.setenv("NINEROUTER_KEY", "")
    assert llm_client.is_configured() is False


def test_model_for_complexity(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_LITE", "kr/claude-haiku-4.5")
    monkeypatch.setenv("LLM_MODEL_FLASH", "my-combo")
    monkeypatch.setenv("LLM_MODEL_PRO", "kr/claude-sonnet-4.5")
    assert llm_client.model_for_complexity("simples") == "kr/claude-haiku-4.5"
    assert llm_client.model_for_complexity("mediana") == "my-combo"
    assert llm_client.model_for_complexity("complexa") == "kr/claude-sonnet-4.5"


def test_extract_text_from_openai_payload():
    payload = {
        "choices": [{"message": {"role": "assistant", "content": "  hello world  "}}]
    }
    assert llm_client._extract_text(payload) == "hello world"


def test_extract_text_from_content_parts():
    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "part "},
                        {"type": "text", "text": "two"},
                    ]
                }
            }
        ]
    }
    assert llm_client._extract_text(payload) == "part two"


def test_complete_posts_openai_payload(monkeypatch):
    monkeypatch.setenv("NINEROUTER_URL", "http://localhost:20128/v1")
    monkeypatch.setenv("NINEROUTER_KEY", "sk-test-key-abcdefghij")
    monkeypatch.setenv("LLM_MODEL", "my-combo")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.ok = True
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "pong"}}]
    }

    with patch("services.llm_client.requests.post", return_value=mock_response) as mock_post:
        text = llm_client.complete("ping", model="my-combo")

    assert text == "pong"
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:20128/v1/chat/completions"
    assert kwargs["json"]["stream"] is False
    assert kwargs["json"]["model"] == "my-combo"
    assert kwargs["json"]["messages"][0]["content"] == "ping"
    assert kwargs["headers"]["Authorization"] == "Bearer sk-test-key-abcdefghij"


def test_complete_raises_when_unconfigured(monkeypatch):
    monkeypatch.setenv("NINEROUTER_KEY", "")
    monkeypatch.delenv("NINEROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(llm_client.LLMUnavailable):
        llm_client.complete("hello")
