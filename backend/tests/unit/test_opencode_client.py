import json

import httpx
import pytest
from cryptography.fernet import InvalidToken

from app.config import Settings
from app.services.ai import AiProviderError, AiTarget
from app.services.opencode import (
    DEFAULT_MODEL,
    INFERENCE_ROOT,
    complete_opencode,
    decrypt_key,
    encrypt_key,
    list_models,
    read_opencode_text,
    require_model,
    verify_key,
)


SECRET = "unit-test-signing-key-0123456789abcdef"
KEY = "oc_sk_test_key_value"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_encrypt_round_trip_and_rotated_secret_fails_closed() -> None:
    token = encrypt_key(KEY, SECRET)
    assert KEY not in token
    assert decrypt_key(token, SECRET) == KEY
    with pytest.raises(InvalidToken):
        decrypt_key(token, "a-different-signing-key-000000000")


def test_require_model_hides_unknown_and_non_chat_ids() -> None:
    assert require_model(" gpt-5.5 ") == "gpt-5.5"
    with pytest.raises(Exception):
        require_model("jev-1.13")
    with pytest.raises(Exception):
        require_model("not-a-model")


def test_list_models_intersects_live_catalog_and_keeps_default_first() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://opencode.ai/inference/v1/models")
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"data": [{"id": "gpt-5.5"}, {"id": "jev-1.13"}, {"id": DEFAULT_MODEL}, {"id": "test"}]})

    models = list_models(_client(handler))
    ids = [item["id"] for item in models]
    assert ids[0] == DEFAULT_MODEL
    assert "gpt-5.5" in ids
    assert "jev-1.13" not in ids
    assert "test" not in ids
    assert models[ids.index("gpt-5.5")]["family"] == "responses"


def test_list_models_falls_back_to_the_static_catalog() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "down"})

    models = list_models(_client(handler))
    assert models[0]["id"] == DEFAULT_MODEL
    assert any(item["id"] == "claude-sonnet-4-6" and item["family"] == "anthropic" for item in models)


def test_verify_key_rejects_unauthorized_without_echoing_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {KEY}"
        return httpx.Response(401, json={"message": KEY})

    with pytest.raises(Exception, match="not accepted") as caught:
        verify_key(KEY, _client(handler))
    assert KEY not in str(caught.value)


def test_complete_opencode_posts_each_text_family() -> None:
    seen: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), json.loads(request.content)))
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(200, json={"choices": [{"message": {"content": "chat-ok"}}]})
        if request.url.path.endswith("/responses"):
            body = {
                "output": [
                    {"type": "reasoning", "content": [{"text": "hidden"}]},
                    {"type": "message", "content": [{"type": "output_text", "text": "responses-ok"}]},
                ]
            }
            return httpx.Response(200, json=body)
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"content": [{"type": "text", "text": "anthropic-ok"}]})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "gemini-ok"}]}}]})

    messages = [
        {"role": "system", "content": "Be brief."},
        {"role": "assistant", "content": "Hello."},
        {"role": "user", "content": "Say ok."},
    ]
    client = _client(handler)
    assert complete_opencode(messages, DEFAULT_MODEL, KEY, client).content == "chat-ok"
    assert complete_opencode(messages, "gpt-5.5", KEY, client).content == "responses-ok"
    assert complete_opencode(messages, "claude-sonnet-4-6", KEY, client).content == "anthropic-ok"
    assert complete_opencode(messages, "gemini-3-flash", KEY, client).content == "gemini-ok"

    chat_url, chat_body = seen[0]
    assert chat_url == f"{INFERENCE_ROOT}/openai/v1/chat/completions"
    assert chat_body["messages"][0]["role"] == "system"
    assert chat_body["temperature"] == 0.2

    _, responses_body = seen[1]
    assert responses_body["instructions"] == "Be brief.\n\nHello."
    assert responses_body["input"] == [{"role": "user", "content": "Say ok."}]
    assert "temperature" not in responses_body

    _, anthropic_body = seen[2]
    assert anthropic_body["system"] == "Be brief.\n\nHello."
    assert anthropic_body["max_tokens"] == 4096
    assert anthropic_body["messages"][0]["role"] == "user"

    gemini_url, gemini_body = seen[3]
    assert gemini_url == f"{INFERENCE_ROOT}/google/v1beta/models/gemini-3-flash:generateContent"
    assert gemini_body["systemInstruction"]["parts"][0]["text"] == "Be brief.\n\nHello."
    assert gemini_body["contents"][0]["role"] == "user"


def test_complete_opencode_rejects_an_unmapped_model_and_empty_reply() -> None:
    with pytest.raises(AiProviderError):
        complete_opencode([{"role": "user", "content": "hi"}], "jev-1.13", KEY)
    client = _client(lambda request: httpx.Response(200, json={"content": "  "}))
    with pytest.raises(AiProviderError):
        complete_opencode([{"role": "user", "content": "hi"}], DEFAULT_MODEL, KEY, client)


def test_read_opencode_text_ignores_reasoning_only_output() -> None:
    assert read_opencode_text({"output": [{"type": "reasoning", "content": [{"text": "hidden"}]}]}) is None


def test_ai_target_marks_only_usable_kinds_ready() -> None:
    from app.services.ai import model_ready

    assert model_ready(Settings(ai_endpoint="", auto_migrate=False), AiTarget("opencode", model_id="gpt-5.5", api_key=KEY))
    assert not model_ready(Settings(ai_endpoint="https://ai.example.test", auto_migrate=False), AiTarget("none"))
    assert model_ready(Settings(ai_endpoint="https://ai.example.test", auto_migrate=False), None)
