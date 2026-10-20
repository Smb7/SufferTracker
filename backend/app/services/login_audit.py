import uuid

from sqlalchemy.orm import Session

from app.models import LoginEvent


def record_login(db: Session, username: str, user_id: uuid.UUID | None, mfa_enabled: bool, succeeded: bool, ip: str) -> None:
    try:
        db.add(LoginEvent(
            user_id=user_id,
            username=username.strip().lower(),
            mfa_enabled=mfa_enabled,
            ip_address=ip,
            succeeded=succeeded,
        ))
        db.commit()
    except Exception:
        db.rollback()
