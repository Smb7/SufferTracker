import uuid

from sqlalchemy.orm import Session

from app.models import LoginEvent
from app.services.geoip import lookup


def record_login(db: Session, username: str, user_id: uuid.UUID | None, mfa_enabled: bool, succeeded: bool, ip: str) -> None:
    try:
        place = lookup(ip)
        db.add(LoginEvent(
            user_id=user_id,
            username=username.strip().lower(),
            mfa_enabled=mfa_enabled,
            ip_address=ip,
            succeeded=succeeded,
            latitude=place.latitude if place else None,
            longitude=place.longitude if place else None,
            city=place.city if place else None,
            country=place.country if place else None,
        ))
        db.commit()
    except Exception:
        db.rollback()
