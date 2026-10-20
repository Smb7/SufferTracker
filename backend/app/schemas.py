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
    created_at: datetime


class LoginEventResponse(APIModel):
    id: UUID
    username: str
    mfa_enabled: bool
    ip_address: str
    succeeded: bool
    occurred_at: datetime
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
