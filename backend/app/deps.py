import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.errors import APIError
from app.models import User
from app.services.tokens import decode_token

_bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError(401, "Not authenticated.")
    try:
        payload = decode_token(credentials.credentials, get_settings())
        user_id = uuid.UUID(str(payload["sub"]))
    except (APIError, ValueError, KeyError, TypeError):
        raise APIError(401, "Not authenticated.") from None
    except Exception:
        raise APIError(401, "Not authenticated.") from None
    user = db.get(User, user_id)
    if user is None:
        raise APIError(401, "Not authenticated.")
    return user
