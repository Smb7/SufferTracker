SECRET = "a" * 12


def _auth(client, email: str) -> dict[str, str]:
    token = client.post("/api/auth/register", json={"email": email, "password": SECRET, "displayName": "Alex"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _say(client, headers: dict[str, str], content: str):
    response = client.post("/api/onboarding/messages", headers=headers, json={"content": content})
    assert response.status_code == 200, response.text
    return response.json()


def test_onboarding_requires_auth(client) -> None:
    assert client.get("/api/onboarding").status_code == 401
    assert client.get("/api/onboarding/context").status_code == 401


def test_onboarding_collects_context_and_isolates_users(client) -> None:
    headers = _auth(client, "coach@example.com")
    first = client.get("/api/onboarding", headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert body["providerConfigured"] is False
    assert body["context"]["status"] == "not_started"
    assert body["context"]["missing"] == ["experience", "education", "skills", "interests", "goals"]
    assert len(body["messages"]) == 1
    assert body["messages"][0]["role"] == "assistant"
    again = client.get("/api/onboarding", headers=headers)
    assert len(again.json()["messages"]) == 1

    early = client.post("/api/onboarding/complete", headers=headers)
    assert early.status_code == 400
    assert early.json()["missing"] == ["experience", "education", "skills", "interests", "goals"]
    assert client.post("/api/onboarding/messages", headers=headers, json={"content": "   "}).status_code == 400

    _say(client, headers, "I was a nurse at Mercy from 2019 to 2023. I ran a 12-bed unit.")
    _say(client, headers, "B.S. in nursing from State University, 2018")
    _say(client, headers, "patient care, triage, and Epic")
    _say(client, headers, "teaching, community health")
    ready = _say(client, headers, "Looking for a clinic manager role, hybrid, around $90k.")
    assert ready["context"]["missing"] == []
    assert ready["context"]["experience"][0]["company"] == "Mercy"
    assert ready["context"]["education"][0]["institution"] == "State University"
    assert ready["context"]["education"][0]["credential"] == "B.S."
    assert "Epic" in ready["context"]["skills"]
    assert ready["context"]["goals"]["targetRoles"] == ["clinic manager"]
    assert ready["context"]["status"] == "in_progress"

    saved = client.post("/api/onboarding/complete", headers=headers)
    assert saved.status_code == 200
    assert saved.json()["context"]["status"] == "completed"
    assert client.get("/api/onboarding/context", headers=headers).json()["status"] == "completed"

    other = _auth(client, "other@example.com")
    other_state = client.get("/api/onboarding", headers=other)
    assert other_state.status_code == 200
    assert len(other_state.json()["messages"]) == 1
    assert "Mercy" not in other_state.json()["messages"][0]["content"]
    assert other_state.json()["context"]["experience"] == []


def test_chat_confirmation_reset_and_manual_edit(client) -> None:
    headers = _auth(client, "edit@example.com")
    client.get("/api/onboarding", headers=headers)
    _say(client, headers, "I was a nurse at Mercy from 2019 to 2023. I ran a 12-bed unit.")
    _say(client, headers, "none")
    _say(client, headers, "patient care, triage")
    _say(client, headers, "teaching")
    _say(client, headers, "Looking for a clinic manager role, remote.")
    confirmed = _say(client, headers, "looks good")
    assert confirmed["context"]["status"] == "completed"

    reopened = client.post("/api/onboarding/reopen", headers=headers)
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "in_progress"

    edited = client.put("/api/onboarding/context", headers=headers, json={"skills": ["Python", "SQL"], "interests": ["maps"]})
    assert edited.status_code == 200
    assert edited.json()["skills"] == ["Python", "SQL"]
    assert "Python" in edited.json()["summary"]

    reset = client.post("/api/onboarding/reset", headers=headers)
    assert reset.status_code == 200
    assert reset.json()["context"]["status"] == "not_started"
    assert reset.json()["context"]["skills"] == []
    assert len(reset.json()["messages"]) == 1
    assert reset.json()["messages"][0]["role"] == "assistant"


def test_delete_account_removes_onboarding(client) -> None:
    headers = _auth(client, "gone@example.com")
    _say(client, headers, "I was a nurse at Mercy from 2019 to 2023. I ran a 12-bed unit.")
    deleted = client.delete("/api/auth/account", headers=headers)
    assert deleted.status_code == 204


def test_message_uses_configured_model(client, monkeypatch) -> None:
    from app.config import Settings
    from app.services.ai import ChatResult

    monkeypatch.setattr(
        "app.routers.onboarding.get_settings",
        lambda: Settings(ai_endpoint="https://ai.example.test/v1/chat/completions", auto_migrate=False, jwt_key="x"),
    )

    def fake(messages, settings=None, client=None):
        assert any(item["role"] == "system" and "invent" in item["content"].lower() for item in messages)
        return ChatResult(
            '{"reply":"State is in. Which skills should I keep?","education":[{"institution":"State","credential":"B.S.","notes":"studied"}]}',
            True,
        )

    monkeypatch.setattr("app.services.onboarding.complete_chat", fake)
    headers = _auth(client, "model@example.com")
    client.get("/api/onboarding", headers=headers)
    state = _say(client, headers, "I studied at State")
    assert state["providerConfigured"] is True
    assert state["context"]["provider"] == "model"
    assert state["context"]["education"][0]["institution"] == "State"
    assert "skills" in state["context"]["missing"]
