import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user
from app.errors import APIError
from app.models import LoginEvent, User
from app.schemas import AdminUserResponse, LoginEventResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise APIError(403, "Admin access is required.")
    return user


def _user_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        mfa_enabled=user.mfa_enabled,
        is_locked=user.is_locked,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


@router.get("/users", response_model=list[AdminUserResponse])
def users(_: User = Depends(admin_user), db: Session = Depends(get_db)) -> list[AdminUserResponse]:
    rows = db.scalars(select(User).order_by(User.email)).all()
    return [_user_response(user) for user in rows]


@router.get("/logins", response_model=list[LoginEventResponse])
def logins(_: User = Depends(admin_user), db: Session = Depends(get_db)) -> list[LoginEventResponse]:
    rows = db.scalars(select(LoginEvent).order_by(LoginEvent.occurred_at.desc()).limit(500)).all()
    return [
        LoginEventResponse(
            id=item.id,
            username=item.username,
            mfa_enabled=item.mfa_enabled,
            ip_address=item.ip_address,
            succeeded=item.succeeded,
            occurred_at=item.occurred_at,
            latitude=item.latitude,
            longitude=item.longitude,
            city=item.city,
            country=item.country,
        )
        for item in rows
    ]


@router.post("/users/{user_id}/lock", response_model=AdminUserResponse)
def lock(user_id: uuid.UUID, actor: User = Depends(admin_user), db: Session = Depends(get_db)) -> AdminUserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise APIError(404, "User not found.")
    if actor.id == user.id:
        raise APIError(400, "You cannot lock your own account.")
    user.is_locked = True
    db.commit()
    db.refresh(user)
    return _user_response(user)


@router.post("/users/{user_id}/unlock", response_model=AdminUserResponse)
def unlock(user_id: uuid.UUID, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> AdminUserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise APIError(404, "User not found.")
    user.is_locked = False
    db.commit()
    db.refresh(user)
    return _user_response(user)


@router.post("/users/{user_id}/reset-mfa", response_model=AdminUserResponse)
def reset_mfa(user_id: uuid.UUID, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> AdminUserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise APIError(404, "User not found.")
    user.mfa_enabled = False
    user.mfa_secret = None
    db.commit()
    db.refresh(user)
    return _user_response(user)
