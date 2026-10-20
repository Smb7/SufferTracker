from datetime import datetime, timedelta, timezone

import jwt

from app.config import Settings
from app.models import User

ROLE_CLAIM = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"


def create_token(user: User, settings: Settings) -> str:
    if not settings.jwt_key:
        raise RuntimeError("Jwt:Key is not configured.")
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
    return jwt.encode(payload, settings.jwt_key, algorithm="HS256")


def decode_token(token: str, settings: Settings) -> dict:
    return jwt.decode(
        token,
        settings.jwt_key,
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        leeway=60,
    )
