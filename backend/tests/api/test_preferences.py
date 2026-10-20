SECRET = "a" * 12


def test_preferences_default_and_update(client) -> None:
    token = client.post("/api/auth/register", json={"email": "prefs@example.com", "password": SECRET, "displayName": "Prefs"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    current = client.get("/api/preferences", headers=headers)
    assert current.status_code == 200
    assert current.json() == {"darkMode": True, "defaultView": "kanban", "interviewRounds": 3}

    updated = client.put("/api/preferences", headers=headers, json={"darkMode": False, "defaultView": "sankey", "interviewRounds": 5})
    assert updated.status_code == 200
    assert updated.json()["darkMode"] is False
    assert updated.json()["defaultView"] == "sankey"
    assert updated.json()["interviewRounds"] == 5

    invalid = client.put("/api/preferences", headers=headers, json={"darkMode": True, "defaultView": "kanban", "interviewRounds": 11})
    assert invalid.status_code == 400
    assert client.get("/api/preferences").status_code == 401
