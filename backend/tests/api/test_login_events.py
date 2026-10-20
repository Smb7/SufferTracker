from app.models import User
from app.services.passwords import hash_password


def test_admin_lists_recent_login_events(client, db, monkeypatch) -> None:
    monkeypatch.setattr("app.services.login_audit.lookup", lambda ip: type("Place", (), {"latitude": 1.5, "longitude": 2.5, "city": "Austin", "country": "United States"})())
    user = User(email="smoke@test.com", password_hash=hash_password("a" * 12), display_name="Admin", is_admin=True)
    db.add(user)
    db.commit()
    signed_in = client.post("/api/auth/login", json={"email": "smoke@test.com", "password": "a" * 12}, headers={"X-Forwarded-For": "8.8.8.8"})
    token = signed_in.json()["token"]
    events = client.get("/api/admin/logins", headers={"Authorization": f"Bearer {token}"})
    assert events.status_code == 200
    assert events.json()[0]["city"] == "Austin"
    assert events.json()[0]["succeeded"] is True
    assert events.json()[0]["ipAddress"] == "8.8.8.8"
