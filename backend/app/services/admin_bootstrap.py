from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import User, UserPreference
from app.services.passwords import hash_password


def ensure_admin(db: Session | None = None, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    owns_session = db is None
    session = db or SessionLocal()
    password = settings.admin_password or ""
    can_set_password = len(password) >= 8
    try:
        for email in settings.admin_email_list:
            user = session.scalar(select(User).where(User.email == email))
            if user is None:
                if not can_set_password:
                    continue
                user = User(email=email, password_hash="", display_name="Admin", is_admin=True)
                user.password_hash = hash_password(password)
                user.preferences = UserPreference(user_id=user.id)
                session.add(user)
                continue
            if not can_set_password:
                continue
            user.is_admin = True
            user.is_locked = False
            user.password_hash = hash_password(password)
        session.commit()
    finally:
        if owns_session:
            session.close()
