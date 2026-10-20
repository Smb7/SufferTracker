from datetime import datetime, timezone

from app.services.totp import generate_code

SECRET = "a" * 12


def _auth_headers(client) -> dict[str, str]:
    response = client.post("/api/auth/register", json={"email": "mfa@example.com", "password": SECRET, "displayName": "MFA"})
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_mfa_setup_enable_and_login_challenge(client) -> None:
    headers = _auth_headers(client)
    assert client.get("/api/auth/mfa/status", headers=headers).json() == {"enabled": False}

    setup = client.post("/api/auth/mfa/setup", headers=headers)
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert setup.json()["otpauthUri"].startswith("otpauth://totp/")
    code = generate_code(secret, datetime.now(timezone.utc))

    enabled = client.post("/api/auth/mfa/enable", headers=headers, json={"code": code})
    assert enabled.status_code == 200
    assert enabled.json() == {"enabled": True}

    challenged = client.post("/api/auth/login", json={"email": "mfa@example.com", "password": SECRET})
    assert challenged.status_code == 401
    assert challenged.json()["mfaRequired"] is True

    signed_in = client.post("/api/auth/login", json={"email": "mfa@example.com", "password": SECRET, "code": code})
    assert signed_in.status_code == 200

    wrong = client.post("/api/auth/mfa/disable", headers=headers, json={"code": "000000"})
    assert wrong.status_code == 400
    disabled = client.post("/api/auth/mfa/disable", headers={"Authorization": f"Bearer {signed_in.json()['token']}"}, json={"code": code})
    assert disabled.status_code == 200
    assert disabled.json() == {"enabled": False}


def test_enable_requires_setup(client) -> None:
    headers = _auth_headers(client)
    response = client.post("/api/auth/mfa/enable", headers=headers, json={"code": "123456"})
    assert response.status_code == 400
    assert "setup" in response.json()["message"]
