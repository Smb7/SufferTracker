import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import current_user
from app.errors import APIError
from app.models import CareerProfile, JobApplication, TailoredResume, User
from app.schemas import (
    FitPreviewRequest,
    FitResponse,
    JobRequirementsResponse,
    JobResponse,
    JobWriteRequest,
    ResumeResponse,
    ResumeWriteRequest,
)
from app.services.evidence import career_evidence, evidence_from_context
from app.services.fit import score_job
from app.services.requirements import extract_requirements
from app.services.opencode import resolve_ai
from app.services.resume import ResumeEditError, accept_edits, evidence_ids, generate_resume
from app.services.timeline import TimelineError, synthesize, validate

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _response(job: JobApplication) -> JobResponse:
    events = job.status_events or []
    return JobResponse(
        id=job.id,
        company=job.company,
        title=job.title,
        description=job.description,
        skills=job.skills,
        pay=job.pay,
        location=job.location,
        nickname=job.nickname,
        source_url=job.source_url,
        status=job.status,
        interview_round=job.interview_round,
        applied_at=job.applied_at,
        updated_at=job.updated_at,
        timeline=[item["status"] if isinstance(item, dict) else item for item in events],
    )


def _apply_timeline(job: JobApplication, body: JobWriteRequest, existing_interviews: int | None = None) -> None:
    try:
        if body.timeline:
            requested = body.timeline
        else:
            round_count = existing_interviews if body.timeline is None else body.interview_round
            requested = synthesize(body.status, round_count)
        events = validate(requested)
    except TimelineError as exc:
        raise APIError(400, str(exc)) from exc
    job.status_events = events
    job.status = events[-1]["status"]
    job.interview_round = sum(1 for item in events if item["status"] == "Interview")


def _source_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise APIError(400, "Source URL must be an HTTP or HTTPS link.")
    return value.strip()


def _owned(db: Session, job_id: uuid.UUID, user_id: uuid.UUID) -> JobApplication:
    job = db.scalar(select(JobApplication).where(JobApplication.id == job_id, JobApplication.user_id == user_id))
    if job is None:
        raise APIError(404, "Application not found.")
    return job


@router.get("", response_model=list[JobResponse])
def list_jobs(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[JobResponse]:
    jobs = db.scalars(select(JobApplication).where(JobApplication.user_id == user.id).order_by(JobApplication.updated_at.desc())).all()
    return [_response(job) for job in jobs]


@router.post("", response_model=JobResponse, status_code=201)
def create_job(body: JobWriteRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> JobResponse:
    if body.status == "Interview" and (body.interview_round is None or body.interview_round < 1 or body.interview_round > 10):
        raise APIError(400, "Interview round must be between 1 and 10.")
    now = datetime.now(timezone.utc)
    job = JobApplication(
        user_id=user.id,
        company=body.company.strip(),
        title=body.title.strip(),
        description=(body.description or "").strip(),
        skills=(body.skills or "").strip(),
        pay=(body.pay or "").strip(),
        location=(body.location or "").strip(),
        nickname=(body.nickname or "").strip(),
        source_url=_source_url(body.source_url),
        applied_at=_aware(body.applied_at) if body.applied_at else now,
        updated_at=now,
        status="Applied",
        status_events=[],
    )
    _apply_timeline(job, body)
    db.add(job)
    db.commit()
    db.refresh(job)
    return _response(job)


def _profile(user: User, db: Session) -> CareerProfile | None:
    profile = user.career_profile
    if profile is None:
        profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    return profile


def _evidence(user: User, db: Session) -> dict:
    profile = _profile(user, db)
    if profile is None:
        return evidence_from_context({"skills": [], "experience": [], "education": [], "interests": [], "goals": {}})
    return career_evidence(profile)


def _education(user: User, db: Session) -> list:
    profile = _profile(user, db)
    if profile is None:
        return []
    return [dict(item) for item in (profile.education or []) if isinstance(item, dict)]


def _resume_row(db: Session, job_id: uuid.UUID, user_id: uuid.UUID) -> TailoredResume | None:
    return db.scalar(select(TailoredResume).where(TailoredResume.job_id == job_id, TailoredResume.user_id == user_id))


def _resume_response(job: JobApplication, row: TailoredResume, evidence: dict) -> ResumeResponse:
    fit = score_job(evidence, title=job.title, company=job.company, description=job.description, skills=job.skills)
    missing = list(fit["missing"]) if fit.get("score") is not None else []
    return ResumeResponse(
        job_id=job.id,
        title=job.title,
        company=job.company,
        score=row.score,
        missing=missing,
        sections=row.sections,
        evidence_ids=list(row.evidence_ids or []),
        updated_at=row.updated_at,
    )


def _fit(user: User, db: Session, *, title: str, company: str, description: str, skills: str) -> FitResponse:
    scored = score_job(_evidence(user, db), title=title, company=company, description=description, skills=skills)
    return FitResponse.model_validate(scored)


@router.post("/fit", response_model=FitResponse)
def preview_fit(
    body: FitPreviewRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FitResponse:
    return _fit(user, db, title=body.title, company=body.company, description=body.description, skills=body.skills)


@router.get("/{job_id}/requirements", response_model=JobRequirementsResponse)
def get_requirements(
    job_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JobRequirementsResponse:
    job = _owned(db, job_id, user.id)
    extracted = extract_requirements(job.title, job.company, job.description, job.skills)
    return JobRequirementsResponse.model_validate(extracted)


@router.get("/{job_id}/fit", response_model=FitResponse)
def get_fit(job_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> FitResponse:
    job = _owned(db, job_id, user.id)
    return _fit(user, db, title=job.title, company=job.company, description=job.description, skills=job.skills)


@router.post("/{job_id}/resume", response_model=ResumeResponse)
def generate_job_resume(job_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ResumeResponse:
    job = _owned(db, job_id, user.id)
    evidence = _evidence(user, db)
    drafted = generate_resume(
        evidence,
        extract_requirements(job.title, job.company, job.description, job.skills),
        education=_education(user, db),
        settings=get_settings(),
        target=resolve_ai(user, db, get_settings()),
    )
    if drafted["blockedReason"]:
        return ResumeResponse(
            job_id=job.id,
            title=job.title,
            company=job.company,
            blocked_reason=drafted["blockedReason"],
            profile_blocked=drafted["profileBlocked"],
        )
    now = datetime.now(timezone.utc)
    sections = drafted["sections"]
    ids = list(drafted["evidenceIds"])
    row = _resume_row(db, job.id, user.id)
    if row is None:
        row = TailoredResume(
            user_id=user.id,
            job_id=job.id,
            score=drafted["score"],
            sections=sections,
            evidence_ids=ids,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.score = drafted["score"]
        row.sections = sections
        row.evidence_ids = ids
        row.updated_at = now
    db.commit()
    db.refresh(row)
    return _resume_response(job, row, evidence)


@router.get("/{job_id}/resume", response_model=ResumeResponse)
def get_resume(job_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ResumeResponse:
    job = _owned(db, job_id, user.id)
    row = _resume_row(db, job.id, user.id)
    if row is None:
        raise APIError(404, "Resume not found.")
    return _resume_response(job, row, _evidence(user, db))


@router.put("/{job_id}/resume", response_model=ResumeResponse)
def save_resume(
    job_id: uuid.UUID,
    body: ResumeWriteRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ResumeResponse:
    job = _owned(db, job_id, user.id)
    row = _resume_row(db, job.id, user.id)
    if row is None:
        raise APIError(404, "Resume not found.")
    evidence = _evidence(user, db)
    try:
        sections = accept_edits(body.sections.model_dump(by_alias=True), evidence, _education(user, db))
    except ResumeEditError as exc:
        raise APIError(400, str(exc)) from exc
    row.sections = sections
    row.evidence_ids = evidence_ids(sections)
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _resume_response(job, row, evidence)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> JobResponse:
    return _response(_owned(db, job_id, user.id))


@router.put("/{job_id}", response_model=JobResponse)
def update_job(job_id: uuid.UUID, body: JobWriteRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> JobResponse:
    job = _owned(db, job_id, user.id)
    existing = sum(1 for item in (job.status_events or []) if isinstance(item, dict) and item.get("status") == "Interview")
    job.company = body.company.strip()
    job.title = body.title.strip()
    job.description = (body.description or "").strip()
    job.skills = (body.skills or "").strip()
    job.pay = (body.pay or "").strip()
    job.location = (body.location or "").strip()
    job.nickname = (body.nickname or "").strip()
    job.source_url = _source_url(body.source_url)
    _apply_timeline(job, body, existing)
    if body.applied_at:
        job.applied_at = _aware(body.applied_at)
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return _response(job)


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    db.delete(_owned(db, job_id, user.id))
    db.commit()
    return Response(status_code=204)
