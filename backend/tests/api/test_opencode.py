from sqlalchemy import select

from app.models import OpenCodeConnection, User
from app.services.ai import AiProviderError, ChatResult
from app.services.opencode import OpenCodeError

SECRET = "a" * 12
KEY = "oc_sk_test_key_value"


def _auth(client) -> dict[str, str]:
    token = client.post(
        "/api/auth/register",
        json={"email": "opencode@example.com", "password": SECRET, "displayName": "Open"},
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _allow(monkeypatch, live: set[str] | None = None) -> None:
    ids = live if live is not None else {"deepseek-v4.1-flash", "gpt-5.5"}

    def verify(api_key: str, client=None) -> set[str]:
        assert api_key
        return ids

    monkeypatch.setattr("app.routers.opencode.verify_key", verify)
    monkeypatch.setattr(
        "app.routers.opencode.list_models",
        lambda client=None, api_key="": [{"id": "deepseek-v4.1-flash", "family": "chat"}, {"id": "gpt-5.5", "family": "responses"}],
    )


def test_opencode_routes_require_auth(client) -> None:
    assert client.get("/api/integrations/opencode").status_code == 401
    assert client.get("/api/integrations/opencode/models").status_code == 401
    assert client.put("/api/integrations/opencode", json={"apiKey": KEY, "modelId": "gpt-5.5"}).status_code == 401


def test_connect_stores_hint_not_key_and_disconnects(client, db, monkeypatch) -> None:
    _allow(monkeypatch)
    headers = _auth(client)
    missing = client.put("/api/integrations/opencode", headers=headers, json={"apiKey": "", "modelId": "gpt-5.5"})
    assert missing.status_code == 400

    connected = client.put(
        "/api/integrations/opencode",
        headers=headers,
        json={"apiKey": KEY, "modelId": "gpt-5.5"},
    )
    assert connected.status_code == 200
    body = connected.json()
    assert body["configured"] is True
    assert body["source"] == "opencode"
    assert body["modelId"] == "gpt-5.5"
    assert body["keyHint"] == "oc_sk_test…"
    assert KEY not in connected.text

    db.expire_all()
    user = db.scalar(select(User).where(User.email == "opencode@example.com"))
    row = db.get(OpenCodeConnection, user.id)
    assert row is not None
    assert KEY not in row.api_key_ciphertext
    assert row.key_hint == "oc_sk_test…"

    kept = client.put("/api/integrations/opencode", headers=headers, json={"apiKey": "  ", "modelId": "deepseek-v4.1-flash"})
    assert kept.status_code == 200
    assert kept.json()["modelId"] == "deepseek-v4.1-flash"
    assert kept.json()["keyHint"] == "oc_sk_test…"

    unknown = client.patch("/api/integrations/opencode", headers=headers, json={"modelId": "jev-1.13"})
    assert unknown.status_code == 400

    assert client.delete("/api/integrations/opencode", headers=headers).status_code == 204
    status = client.get("/api/integrations/opencode", headers=headers)
    assert status.json()["configured"] is False
    assert status.json()["source"] == "none"
    db.expire_all()
    assert db.get(OpenCodeConnection, user.id) is None


def test_model_change_and_connection_test(client, monkeypatch) -> None:
    _allow(monkeypatch)
    headers = _auth(client)
    client.put("/api/integrations/opencode", headers=headers, json={"apiKey": KEY, "modelId": "gpt-5.5"})
    changed = client.patch("/api/integrations/opencode", headers=headers, json={"modelId": "deepseek-v4.1-flash"})
    assert changed.status_code == 200
    assert changed.json()["modelId"] == "deepseek-v4.1-flash"

    monkeypatch.setattr("app.routers.opencode.complete_opencode", lambda *args, **kwargs: ChatResult("ok", True))
    tested = client.post("/api/integrations/opencode/test", headers=headers)
    assert tested.status_code == 200
    assert tested.json() == {"ok": True, "message": "OpenCode replied."}

    def fail(*args, **kwargs):
        raise AiProviderError("OpenCode rejected the API key.")

    monkeypatch.setattr("app.routers.opencode.complete_opencode", fail)
    failed = client.post("/api/integrations/opencode/test", headers=headers)
    assert failed.status_code == 200
    assert failed.json()["ok"] is False
    assert "rejected" in failed.json()["message"]
    status = client.get("/api/integrations/opencode", headers=headers)
    assert "rejected" in status.json()["lastError"]
    assert client.post("/api/integrations/opencode/test").status_code == 401


def test_refused_model_is_unavailable_and_not_stored(client, db, monkeypatch) -> None:
    _allow(monkeypatch, {"gpt-5.5"})
    headers = _auth(client)
    refused = client.put(
        "/api/integrations/opencode",
        headers=headers,
        json={"apiKey": KEY, "modelId": "deepseek-v4.1-flash"},
    )
    assert refused.status_code == 400
    assert "not available" in refused.json()["message"]
    assert "not accepted" not in refused.json()["message"]
    assert KEY not in refused.text
    db.expire_all()
    user = db.scalar(select(User).where(User.email == "opencode@example.com"))
    assert db.get(OpenCodeConnection, user.id) is None

    connected = client.put("/api/integrations/opencode", headers=headers, json={"apiKey": KEY, "modelId": "gpt-5.5"})
    assert connected.status_code == 200
    blocked = client.patch("/api/integrations/opencode", headers=headers, json={"modelId": "deepseek-v4.1-flash"})
    assert blocked.status_code == 400
    assert "not available" in blocked.json()["message"]
    assert client.get("/api/integrations/opencode", headers=headers).json()["modelId"] == "gpt-5.5"


def test_models_are_listed_with_the_saved_or_preview_key(client, monkeypatch) -> None:
    seen: dict[str, str] = {}

    def listing(client=None, api_key: str = "") -> list[dict[str, str]]:
        seen["key"] = api_key
        return [{"id": "gpt-5.5", "family": "responses"}]

    _allow(monkeypatch)
    monkeypatch.setattr("app.routers.opencode.list_models", listing)
    headers = _auth(client)
    client.put("/api/integrations/opencode", headers=headers, json={"apiKey": KEY, "modelId": "gpt-5.5"})
    listed = client.get("/api/integrations/opencode/models", headers=headers)
    assert listed.status_code == 200
    assert listed.json() == [{"id": "gpt-5.5", "family": "responses"}]
    assert seen["key"] == KEY

    preview = client.get("/api/integrations/opencode/models", headers={**headers, "X-OpenCode-Key": "oc_sk_preview_key"})
    assert preview.status_code == 200
    assert seen["key"] == "oc_sk_preview_key"


def test_bad_key_is_rejected_and_not_stored(client, db, monkeypatch) -> None:
    def reject(api_key: str, client=None) -> set[str]:
        raise OpenCodeError("That API key was not accepted.", 400)

    monkeypatch.setattr("app.routers.opencode.verify_key", reject)
    headers = _auth(client)
    rejected = client.put("/api/integrations/opencode", headers=headers, json={"apiKey": KEY, "modelId": "gpt-5.5"})
    assert rejected.status_code == 400
    assert KEY not in rejected.text
    db.expire_all()
    user = db.scalar(select(User).where(User.email == "opencode@example.com"))
    assert db.get(OpenCodeConnection, user.id) is None


def test_onboarding_uses_user_connection_without_env_endpoint(client, monkeypatch) -> None:
    _allow(monkeypatch)
    seen: dict[str, str] = {}

    def fake(messages, model_id, api_key, client=None):
        seen["model"] = model_id
        seen["key"] = api_key
        assert any(item["role"] == "system" for item in messages)
        return ChatResult('{"reply":"Noted. Which skills should I keep?","skills":["Python"]}', True)

    def env_provider(*args, **kwargs):
        raise AssertionError("environment provider was used")

    monkeypatch.setattr("app.services.onboarding.complete_opencode", fake)
    monkeypatch.setattr("app.services.onboarding.complete_chat", env_provider)
    headers = _auth(client)
    client.put("/api/integrations/opencode", headers=headers, json={"apiKey": KEY, "modelId": "gpt-5.5"})
    opened = client.get("/api/onboarding", headers=headers)
    assert opened.json()["providerConfigured"] is True
    state = client.post("/api/onboarding/messages", headers=headers, json={"content": "I write Python services."})
    assert state.status_code == 200
    assert state.json()["context"]["provider"] == "model"
    assert seen == {"model": "gpt-5.5", "key": KEY}


def test_delete_account_removes_opencode_connection(client, db, monkeypatch) -> None:
    _allow(monkeypatch)
    headers = _auth(client)
    client.put("/api/integrations/opencode", headers=headers, json={"apiKey": KEY, "modelId": "gpt-5.5"})
    assert client.delete("/api/auth/account", headers=headers).status_code == 204
    db.expire_all()
    user = db.scalar(select(User).where(User.email == "opencode@example.com"))
    assert user is None
    assert db.scalar(select(OpenCodeConnection)) is None
