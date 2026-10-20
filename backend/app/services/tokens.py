from datetime import datetime, timedelta, timezone

import jwt

from app.config import Settings
from app.models import User

ROLE_CLAIM = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"


def _signing_key(settings: Settings) -> str:
    key = settings.jwt_key or ""
    if len(key) < 32:
        raise RuntimeError("Jwt:Key is not configured.")
    return key


def create_token(user: User, settings: Settings) -> str:
    key = _signing_key(settings)
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "sub": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(hours=12),
    }
    if user.is_admin:
        payload["role"] = "Admin"
        payload[ROLE_CLAIM] = "Admin"
    return jwt.encode(payload, key, algorithm="HS256")


def decode_token(token: str, settings: Settings) -> dict:
    return jwt.decode(
        token,
        _signing_key(settings),
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        leeway=60,
    )
