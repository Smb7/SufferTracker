from app.models import LoginEvent, User
from app.services.passwords import hash_password

SECRET = "a" * 12


def _register(client, email="person@example.com", password=SECRET, display_name="Person"):
    return client.post("/api/auth/register", json={"email": email, "password": password, "displayName": display_name})


def test_register_and_login_round_trip(client, db) -> None:
    created = _register(client)
    assert created.status_code == 200
    body = created.json()
    assert body["email"] == "person@example.com"
    assert body["displayName"] == "Person"
    assert body["isAdmin"] is False
    assert body["token"]

    signed_in = client.post("/api/auth/login", json={"email": "person@example.com", "password": SECRET})
    assert signed_in.status_code == 200
    event = db.query(LoginEvent).one()
    assert event.succeeded is True
    assert event.username == "person@example.com"
    assert event.mfa_enabled is False


def test_register_rejects_short_password_and_duplicate_email(client) -> None:
    short = _register(client, password="short")
    assert short.status_code == 400
    assert "password" in short.json()["message"]

    assert _register(client, email="smoke@test.com").status_code == 200
    duplicate = _register(client, email="Smoke@test.com")
    assert duplicate.status_code == 409
    assert duplicate.json()["message"]


def test_register_marks_configured_admin(client) -> None:
    response = _register(client, email="smoke@test.com", display_name="Smoke")
    assert response.status_code == 200
    assert response.json()["isAdmin"] is True


def test_login_unknown_user_is_failure_without_user_id(client, db) -> None:
    response = client.post("/api/auth/login", json={"email": "missing@test.com", "password": SECRET})
    assert response.status_code == 401
    event = db.query(LoginEvent).one()
    assert event.succeeded is False
    assert event.user_id is None


def test_login_rejects_locked_account_and_records_failure(client, db) -> None:
    user = User(email="locked@test.com", password_hash=hash_password(SECRET), display_name="Locked", is_locked=True)
    db.add(user)
    db.commit()

    response = client.post("/api/auth/login", json={"email": user.email, "password": SECRET})
    assert response.status_code == 403
    assert "locked" in response.json()["message"]
    event = db.query(LoginEvent).one()
    assert event.succeeded is False
    assert event.username == user.email


def test_profile_update_and_account_delete(client) -> None:
    token = _register(client).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    updated = client.put("/api/auth/profile", headers=headers, json={"displayName": "Updated", "email": "updated@example.com", "newPassword": "b" * 12})
    assert updated.status_code == 200
    assert updated.json()["displayName"] == "Updated"
    assert updated.json()["email"] == "updated@example.com"

    resigned = client.post("/api/auth/login", json={"email": "updated@example.com", "password": "b" * 12})
    assert resigned.status_code == 200

    conflict = client.put("/api/auth/profile", headers={"Authorization": f"Bearer {updated.json()['token']}"}, json={"displayName": "X", "email": "updated@example.com"})
    assert conflict.status_code == 200

    other = _register(client, email="other@example.com").json()["token"]
    taken = client.put("/api/auth/profile", headers={"Authorization": f"Bearer {other}"}, json={"displayName": "Other", "email": "updated@example.com"})
    assert taken.status_code == 409

    missing = client.put("/api/auth/profile", json={"displayName": "X", "email": "x@example.com"})
    assert missing.status_code == 401

    deleted = client.delete("/api/auth/account", headers={"Authorization": f"Bearer {updated.json()['token']}"})
    assert deleted.status_code == 204
    assert client.post("/api/auth/login", json={"email": "updated@example.com", "password": "b" * 12}).status_code == 401
