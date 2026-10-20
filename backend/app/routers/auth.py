from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import current_user
from app.errors import APIError
from app.models import User, UserPreference
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UpdateProfileRequest
from app.services.client_ip import client_ip
from app.services.login_audit import record_login
from app.services.passwords import hash_password, verify_password
from app.services.tokens import create_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _is_configured_admin(email: str) -> bool:
    return email in get_settings().admin_email_list


def _response(user: User) -> AuthResponse:
    return AuthResponse(token=create_token(user, get_settings()), user_id=user.id, email=user.email, display_name=user.display_name, is_admin=user.is_admin)


@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = _normalize_email(body.email)
    if not email or len(body.password) < 8:
        raise APIError(400, "Email is required and password must be at least 8 characters.")
    if db.scalar(select(User).where(User.email == email)):
        raise APIError(409, "An account with that email already exists.")
    user = User(email=email, password_hash="", display_name=body.display_name.strip(), is_admin=_is_configured_admin(email))
    user.password_hash = hash_password(body.password)
    user.preferences = UserPreference(user_id=user.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _response(user)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    username = _normalize_email(body.email)
    ip = client_ip(request)
    user = db.scalar(select(User).where(User.email == username))
    if user is None or not verify_password(user.password_hash, body.password):
        record_login(db, username, user.id if user else None, user.mfa_enabled if user else False, False, ip)
        raise APIError(401, "Invalid email or password.")
    if user.is_locked:
        record_login(db, username, user.id, user.mfa_enabled, False, ip)
        raise APIError(403, "This account is locked.")
    record_login(db, username, user.id, user.mfa_enabled, True, ip)
    return _response(user)


@router.put("/profile", response_model=AuthResponse)
def update_profile(body: UpdateProfileRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> AuthResponse:
    email = _normalize_email(body.email)
    existing = db.scalar(select(User).where(User.email == email, User.id != user.id))
    if existing is not None:
        raise APIError(409, "That email is already in use.")
    user.email = email
    user.display_name = body.display_name.strip()
    if body.new_password and body.new_password.strip():
        user.password_hash = hash_password(body.new_password)
    db.commit()
    db.refresh(user)
    return _response(user)


@router.delete("/account", status_code=204)
def delete_account(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    db.delete(user)
    db.commit()
    return Response(status_code=204)
