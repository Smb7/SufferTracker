from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def to_camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RegisterRequest(APIModel):
    email: str
    password: str
    display_name: str = ""


class LoginRequest(APIModel):
    email: str
    password: str
    code: str | None = None


class UpdateProfileRequest(APIModel):
    display_name: str
    email: str
    new_password: str | None = None


class AuthResponse(APIModel):
    token: str
    user_id: UUID
    email: str
    display_name: str
    is_admin: bool


class MfaSetupResponse(APIModel):
    secret: str
    otpauth_uri: str


class MfaStatusResponse(APIModel):
    enabled: bool


class MfaCodeRequest(APIModel):
    code: str


class PreferencesResponse(APIModel):
    dark_mode: bool
    default_view: str
    interview_rounds: int


class UpdatePreferencesRequest(APIModel):
    dark_mode: bool
    default_view: str
    interview_rounds: int


class AdminUserResponse(APIModel):
    id: UUID
    email: str
    display_name: str
    mfa_enabled: bool
    is_locked: bool
    is_admin: bool
    created_at: datetime = Field(alias="createdAtUtc")


class LoginEventResponse(APIModel):
    id: UUID
    username: str
    mfa_enabled: bool
    ip_address: str
    succeeded: bool
    occurred_at: datetime = Field(alias="occurredAtUtc")
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    country: str | None = None


class ParsedJobResponse(APIModel):
    company: str
    title: str
    description: str
    skills: str
    pay: str
    location: str
    source_url: str | None = None
    notice: str | None = None


class JobWriteRequest(APIModel):
    company: str
    title: str
    description: str | None = None
    skills: str | None = None
    pay: str | None = None
    location: str | None = None
    nickname: str | None = None
    source_url: str | None = None
    status: str
    interview_round: int | None = None
    applied_at: datetime | None = Field(default=None, alias="appliedAtUtc")
    timeline: list[str] | None = None


class JobResponse(APIModel):
    id: UUID
    company: str
    title: str
    description: str
    skills: str
    pay: str
    location: str
    nickname: str
    source_url: str | None = None
    status: str
    interview_round: int | None = None
    applied_at: datetime = Field(alias="appliedAtUtc")
    updated_at: datetime = Field(alias="updatedAtUtc")
    timeline: list[str]


class PublicStatsResponse(APIModel):
    applications_this_week: int


class ExperienceItem(APIModel):
    title: str = ""
    company: str = ""
    start: str = ""
    end: str = ""
    highlights: str = ""


class EducationItem(APIModel):
    institution: str = ""
    credential: str = ""
    field: str = ""
    year: str = ""
    notes: str = ""


class CareerGoals(APIModel):
    target_roles: list[str] = []
    industries: list[str] = []
    locations: list[str] = []
    work_style: str = ""
    compensation: str = ""
    timeline: str = ""
    narrative: str = ""
    constraints: str = ""


class CareerContextResponse(APIModel):
    status: str
    summary: str
    experience: list[ExperienceItem]
    education: list[EducationItem]
    skills: list[str]
    interests: list[str]
    goals: CareerGoals
    missing: list[str]
    provider: str
    notice: str
    updated_at: datetime = Field(alias="updatedAtUtc")


class OnboardingMessageResponse(APIModel):
    id: UUID
    role: str
    content: str
    created_at: datetime = Field(alias="createdAtUtc")


class OnboardingStateResponse(APIModel):
    context: CareerContextResponse
    messages: list[OnboardingMessageResponse]
    provider_configured: bool


class OnboardingMessageRequest(APIModel):
    content: str


class UpdateCareerContextRequest(APIModel):
    summary: str | None = None
    experience: list[ExperienceItem] | None = None
    education: list[EducationItem] | None = None
    skills: list[str] | None = None
    interests: list[str] | None = None
    goals: CareerGoals | None = None


class JobRequirementsResponse(APIModel):
    title: str
    company: str
    required: list[str]
    preferred: list[str]
    keywords: list[str]
    blocked_reason: str | None = None


class FitMatch(APIModel):
    term: str
    source: str


class FitResponse(APIModel):
    score: int | None = None
    blocked_reason: str | None = None
    profile_blocked: bool = False
    matched: list[FitMatch] = []
    missing: list[str] = []
    title_alignment: float | None = None


class FitPreviewRequest(APIModel):
    title: str = ""
    company: str = ""
    description: str = ""
    skills: str = ""


class ResumeBullet(APIModel):
    evidence_id: str
    text: str = ""


class ResumeSkill(APIModel):
    evidence_id: str
    text: str = ""


class ResumeRoleSection(APIModel):
    role_id: int
    title: str = ""
    company: str = ""
    start: str = ""
    end: str = ""
    bullets: list[ResumeBullet] = []


class ResumeEducationSection(APIModel):
    evidence_id: str
    institution: str = ""
    credential: str = ""
    field: str = ""
    year: str = ""
    text: str = ""


class ResumeSections(APIModel):
    summary: str = ""
    skills: list[ResumeSkill] = []
    experience: list[ResumeRoleSection] = []
    education: list[ResumeEducationSection] = []


class ResumeWriteRequest(APIModel):
    sections: ResumeSections


class OpenCodeStatusResponse(APIModel):
    configured: bool
    key_hint: str = ""
    model_id: str = ""
    source: str
    last_checked_at: datetime | None = Field(default=None, alias="lastCheckedAtUtc")
    last_error: str = ""


class OpenCodeModelResponse(APIModel):
    id: str
    family: str


class OpenCodeConnectRequest(APIModel):
    api_key: str = ""
    model_id: str


class OpenCodeModelRequest(APIModel):
    model_id: str


class OpenCodeTestResponse(APIModel):
    ok: bool
    message: str


class ResumeResponse(APIModel):
    job_id: UUID | None = None
    title: str = ""
    company: str = ""
    score: int | None = None
    blocked_reason: str | None = None
    profile_blocked: bool = False
    missing: list[str] = []
    sections: ResumeSections | None = None
    evidence_ids: list[str] = []
    updated_at: datetime | None = Field(default=None, alias="updatedAtUtc")
