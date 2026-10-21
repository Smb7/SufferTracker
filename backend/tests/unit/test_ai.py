import json

import httpx
import pytest

from app.config import Settings
from app.services.ai import AiProviderError, complete_chat


def test_complete_chat_reads_openai_shape_and_prefixes_bearer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret"
        body = json.loads(request.content)
        assert body["model"] == "coach"
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(200, json={"choices": [{"message": {"content": [{"type": "text", "text": "{\"reply\":\"ok\"}"}]}}]})

    settings = Settings(ai_endpoint="https://ai.example.test/v1/chat/completions", ai_api_key="secret", ai_model="coach", auto_migrate=False)
    result = complete_chat([{"role": "system", "content": "coach"}], settings, httpx.Client(transport=httpx.MockTransport(handler)))
    assert result.provider_used is True
    assert result.content == '{"reply":"ok"}'


def test_complete_chat_requires_an_endpoint() -> None:
    with pytest.raises(AiProviderError):
        complete_chat([{"role": "user", "content": "hi"}], Settings(ai_endpoint="", auto_migrate=False))


def test_complete_chat_rejects_empty_provider_content() -> None:
    settings = Settings(ai_endpoint="https://ai.example.test/chat", auto_migrate=False)
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"content": "  "})))
    with pytest.raises(AiProviderError):
        complete_chat([{"role": "user", "content": "hi"}], settings, client)
