from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
import pytest

from app.config import Settings
from app.models import User
from app.services.tokens import ROLE_CLAIM, create_token

KEY = "unit-test-signing-key-0123456789abcdef"
SETTINGS = Settings(jwt_key=KEY, jwt_issuer="SufferTracker.Tests", jwt_audience="SufferTracker.Tests.Clients", auto_migrate=False)


def _user(**overrides) -> User:
    data = {"email": "shane@example.com", "password_hash": "x", "display_name": "Shane B"}
    data.update(overrides)
    return User(**data)


def test_create_token_includes_user_claims_without_admin_role() -> None:
    user = _user(id=UUID("2c1f7a52-1b3e-4d5f-9a01-77aa88bb99cc"))
    claims = jwt.decode(create_token(user, SETTINGS), KEY, algorithms=["HS256"], audience="SufferTracker.Tests.Clients", issuer="SufferTracker.Tests")

    assert claims["sub"] == str(user.id)
    assert claims["email"] == "shane@example.com"
    assert claims["display_name"] == "Shane B"
    assert claims["iss"] == "SufferTracker.Tests"
    assert claims["aud"] == "SufferTracker.Tests.Clients"
    assert "role" not in claims
    assert ROLE_CLAIM not in claims


def test_create_token_expires_within_twelve_hours() -> None:
    token = create_token(_user(), SETTINGS)
    claims = jwt.decode(token, KEY, algorithms=["HS256"], audience="SufferTracker.Tests.Clients", issuer="SufferTracker.Tests")
    remaining = datetime.fromtimestamp(claims["exp"], timezone.utc) - datetime.now(timezone.utc)
    assert timedelta(hours=11.5) <= remaining <= timedelta(hours=12)


def test_create_token_admin_includes_role_claim() -> None:
    claims = jwt.decode(create_token(_user(email="admin@example.com", is_admin=True), SETTINGS), KEY, algorithms=["HS256"], audience="SufferTracker.Tests.Clients")
    assert claims["role"] == "Admin"
    assert claims[ROLE_CLAIM] == "Admin"


def test_create_token_missing_key_raises() -> None:
    with pytest.raises(RuntimeError):
        create_token(_user(), Settings(jwt_key="", auto_migrate=False))
