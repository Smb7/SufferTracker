from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import current_user
from app.errors import APIError
from app.models import CareerProfile, OnboardingMessage, User, utcnow
from app.schemas import (
    CareerContextResponse,
    CareerGoals,
    EducationItem,
    ExperienceItem,
    OnboardingMessageRequest,
    OnboardingMessageResponse,
    OnboardingStateResponse,
    UpdateCareerContextRequest,
)
from app.services.onboarding import OPENING, apply_context_update, apply_user_turn, empty_goals, missing_sections
from app.services.opencode import resolve_ai

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


def _goals(raw: dict | None) -> CareerGoals:
    data = {**empty_goals(), **(raw or {})}
    return CareerGoals(
        target_roles=list(data.get("targetRoles") or []),
        industries=list(data.get("industries") or []),
        locations=list(data.get("locations") or []),
        work_style=str(data.get("workStyle") or ""),
        compensation=str(data.get("compensation") or ""),
        timeline=str(data.get("timeline") or ""),
        narrative=str(data.get("narrative") or ""),
        constraints=str(data.get("constraints") or ""),
    )


def _context(profile: CareerProfile) -> CareerContextResponse:
    return CareerContextResponse(
        status=profile.status,
        summary=profile.summary or "",
        experience=[ExperienceItem(**item) for item in profile.experience or [] if isinstance(item, dict)],
        education=[EducationItem(**item) for item in profile.education or [] if isinstance(item, dict)],
        skills=list(profile.skills or []),
        interests=list(profile.interests or []),
        goals=_goals(profile.goals),
        missing=missing_sections(profile),
        provider=profile.provider or "guided",
        notice=profile.notice or "",
        updated_at=profile.updated_at,
    )


def _configured(user: User, db: Session) -> bool:
    return resolve_ai(user, db, get_settings()).kind in {"opencode", "env"}


def _state(profile: CareerProfile, messages: list[OnboardingMessage], provider_configured: bool) -> OnboardingStateResponse:
    return OnboardingStateResponse(
        context=_context(profile),
        messages=[
            OnboardingMessageResponse(id=item.id, role=item.role, content=item.content, created_at=item.created_at)
            for item in messages
        ],
        provider_configured=provider_configured,
    )


def _messages(db: Session, user: User) -> list[OnboardingMessage]:
    return list(db.scalars(select(OnboardingMessage).where(OnboardingMessage.user_id == user.id).order_by(OnboardingMessage.seq)))


def _profile(user: User, db: Session) -> CareerProfile | None:
    if user.career_profile is not None:
        return user.career_profile
    return db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))


def _ensure(user: User, db: Session) -> CareerProfile:
    profile = _profile(user, db)
    if profile is None:
        profile = CareerProfile(user_id=user.id, goals=empty_goals(), experience=[], education=[], skills=[], interests=[], acknowledged={})
        db.add(profile)
        db.flush()
    return profile


def _ensure_opening(user: User, db: Session, profile: CareerProfile) -> list[OnboardingMessage]:
    messages = _messages(db, user)
    if messages:
        return messages
    db.add(OnboardingMessage(user_id=user.id, seq=1, role="assistant", content=OPENING, created_at=utcnow()))
    profile.updated_at = utcnow()
    db.commit()
    db.refresh(profile)
    return _messages(db, user)


@router.get("/context", response_model=CareerContextResponse)
def get_context(user: User = Depends(current_user), db: Session = Depends(get_db)) -> CareerContextResponse:
    profile = _profile(user, db)
    if profile is None:
        now = utcnow()
        return CareerContextResponse(
            status="not_started",
            summary="",
            experience=[],
            education=[],
            skills=[],
            interests=[],
            goals=_goals(None),
            missing=["experience", "education", "skills", "interests", "goals"],
            provider="guided",
            notice="",
            updated_at=now,
        )
    return _context(profile)


@router.get("", response_model=OnboardingStateResponse)
def get_onboarding(user: User = Depends(current_user), db: Session = Depends(get_db)) -> OnboardingStateResponse:
    profile = _ensure(user, db)
    return _state(profile, _ensure_opening(user, db, profile), _configured(user, db))


@router.put("/context", response_model=CareerContextResponse)
def update_context(body: UpdateCareerContextRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> CareerContextResponse:
    profile = _ensure(user, db)
    apply_context_update(
        profile,
        summary=body.summary,
        experience=[item.model_dump() for item in body.experience] if body.experience is not None else None,
        education=[item.model_dump() for item in body.education] if body.education is not None else None,
        skills=body.skills,
        interests=body.interests,
        goals=body.goals.model_dump(by_alias=True) if body.goals is not None else None,
    )
    profile.updated_at = utcnow()
    db.commit()
    db.refresh(profile)
    return _context(profile)


@router.post("/messages", response_model=OnboardingStateResponse)
def post_message(body: OnboardingMessageRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> OnboardingStateResponse:
    content = body.content.strip()
    if not content:
        raise APIError(400, "Write a message before sending.")
    if len(content) > 8000:
        raise APIError(400, "That message is too long.")
    profile = _ensure(user, db)
    messages = _ensure_opening(user, db, profile)
    history = [(item.role, item.content) for item in messages]
    target = resolve_ai(user, db, get_settings())
    result = apply_user_turn(profile, content, history, get_settings(), target=target)
    profile.provider = result.provider
    profile.notice = result.notice
    profile.updated_at = utcnow()
    if result.completed and not missing_sections(profile):
        profile.status = "completed"
        profile.completed_at = profile.completed_at or utcnow()
    else:
        profile.status = "in_progress"
        profile.completed_at = None
    seq = messages[-1].seq + 1 if messages else 1
    db.add(OnboardingMessage(user_id=user.id, seq=seq, role="user", content=content, created_at=utcnow()))
    db.add(OnboardingMessage(user_id=user.id, seq=seq + 1, role="assistant", content=result.reply, created_at=utcnow()))
    db.commit()
    db.refresh(profile)
    return _state(profile, _messages(db, user), _configured(user, db))


@router.post("/complete", response_model=OnboardingStateResponse)
def complete_onboarding(user: User = Depends(current_user), db: Session = Depends(get_db)) -> OnboardingStateResponse:
    profile = _ensure(user, db)
    missing = missing_sections(profile)
    if missing:
        raise APIError(400, "Onboarding still needs a few answers.", missing=missing)
    profile.status = "completed"
    profile.completed_at = profile.completed_at or utcnow()
    profile.updated_at = utcnow()
    profile.notice = ""
    db.commit()
    db.refresh(profile)
    return _state(profile, _messages(db, user), _configured(user, db))


@router.post("/reopen", response_model=CareerContextResponse)
def reopen_onboarding(user: User = Depends(current_user), db: Session = Depends(get_db)) -> CareerContextResponse:
    profile = _ensure(user, db)
    profile.status = "in_progress"
    profile.completed_at = None
    profile.updated_at = utcnow()
    db.commit()
    db.refresh(profile)
    return _context(profile)


@router.post("/reset", response_model=OnboardingStateResponse)
def reset_onboarding(user: User = Depends(current_user), db: Session = Depends(get_db)) -> OnboardingStateResponse:
    profile = _ensure(user, db)
    db.execute(delete(OnboardingMessage).where(OnboardingMessage.user_id == user.id))
    profile.status = "not_started"
    profile.summary = ""
    profile.experience = []
    profile.education = []
    profile.skills = []
    profile.interests = []
    profile.goals = empty_goals()
    profile.acknowledged = {}
    profile.provider = "guided"
    profile.notice = ""
    profile.completed_at = None
    profile.updated_at = utcnow()
    db.add(OnboardingMessage(user_id=user.id, seq=1, role="assistant", content=OPENING, created_at=utcnow()))
    db.commit()
    db.refresh(profile)
    return _state(profile, _messages(db, user), _configured(user, db))
