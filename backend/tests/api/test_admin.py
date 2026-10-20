from uuid import UUID

from sqlalchemy import select

from app.config import Settings
from app.models import User
from app.services.admin_bootstrap import ensure_admin
from app.services.passwords import hash_password, verify_password

SECRET = "a" * 12


def _token(client, db, email: str, admin: bool = False) -> str:
    response = client.post("/api/auth/register", json={"email": email, "password": SECRET, "displayName": email.split("@")[0]})
    assert response.status_code == 200
    if admin:
        user = db.scalar(select(User).where(User.email == email))
        user.is_admin = True
        db.commit()
    return response.json()["token"]


def test_admin_lock_unlock_and_reset_mfa(client, db) -> None:
    admin = _token(client, db, "ops@test.com", admin=True)
    member = client.post("/api/auth/register", json={"email": "member@test.com", "password": SECRET, "displayName": "Member"})
    member_id = member.json()["userId"]
    user = db.get(User, UUID(member_id))
    user.mfa_enabled = True
    user.mfa_secret = "secret"
    db.commit()

    headers = {"Authorization": f"Bearer {admin}"}
    locked = client.post(f"/api/admin/users/{member_id}/lock", headers=headers)
    assert locked.status_code == 200
    assert locked.json()["isLocked"] is True

    reset = client.post(f"/api/admin/users/{member_id}/reset-mfa", headers=headers)
    assert reset.json()["mfaEnabled"] is False
    db.refresh(user)
    assert user.mfa_secret is None

    unlocked = client.post(f"/api/admin/users/{member_id}/unlock", headers=headers)
    assert unlocked.json()["isLocked"] is False

    listed = client.get("/api/admin/users", headers=headers)
    assert listed.status_code == 200
    assert {item["email"] for item in listed.json()} == {"member@test.com", "ops@test.com"}


def test_admin_cannot_lock_self_and_member_is_forbidden(client, db) -> None:
    admin = client.post("/api/auth/register", json={"email": "ops@test.com", "password": SECRET, "displayName": "Admin"}).json()
    user = db.scalar(select(User).where(User.email == "ops@test.com"))
    user.is_admin = True
    db.commit()
    denied = client.post(f"/api/admin/users/{admin['userId']}/lock", headers={"Authorization": f"Bearer {admin['token']}"})
    assert denied.status_code == 400
    assert "own account" in denied.json()["message"]

    member = client.post("/api/auth/register", json={"email": "member@test.com", "password": SECRET, "displayName": "Member"}).json()
    forbidden = client.get("/api/admin/users", headers={"Authorization": f"Bearer {member['token']}"})
    assert forbidden.status_code == 403


def test_bootstrap_does_not_promote_existing_user_without_password(db) -> None:
    user = User(email="ops@test.com", password_hash=hash_password("e" * 12), display_name="Ops", is_admin=False)
    db.add(user)
    db.commit()
    ensure_admin(db, Settings(admin_emails="ops@test.com", admin_password="", auto_migrate=False, database_url="sqlite://"))
    db.refresh(user)
    assert user.is_admin is False
    assert verify_password(user.password_hash, "e" * 12)


def test_bootstrap_creates_admin_when_missing(db) -> None:
    created = "c" * 12
    ensure_admin(db, Settings(admin_emails="ops@test.com", admin_password=created, auto_migrate=False, database_url="sqlite://"))
    user = db.query(User).filter_by(email="ops@test.com").one()
    assert user.is_admin is True
    assert verify_password(user.password_hash, created)
    assert user.preferences is not None


def test_bootstrap_resets_password_and_unlocks_existing_admin(db) -> None:
    rotated = "d" * 12
    user = User(email="ops@test.com", password_hash=hash_password("e" * 12), display_name="Ops", is_locked=True)
    db.add(user)
    db.commit()
    ensure_admin(db, Settings(admin_emails="ops@test.com", admin_password=rotated, auto_migrate=False, database_url="sqlite://"))
    db.refresh(user)
    assert user.is_admin is True
    assert user.is_locked is False
    assert verify_password(user.password_hash, rotated)
