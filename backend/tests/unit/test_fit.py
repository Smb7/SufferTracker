import uuid

from app.models import CareerProfile
from app.services.evidence import career_evidence
from app.services.fit import FINISH_ONBOARDING, score_fit, title_alignment
from app.services.requirements import NO_TERMS, extract_requirements


def _profile(**overrides) -> CareerProfile:
    data = {
        "user_id": uuid.uuid4(),
        "status": "completed",
        "summary": "",
        "experience": [],
        "education": [],
        "skills": [],
        "interests": [],
        "goals": {},
        "acknowledged": {},
        "provider": "guided",
        "notice": "",
    }
    data.update(overrides)
    return CareerProfile(**data)


def _engineer() -> CareerProfile:
    return _profile(
        skills=["Python", "PostgreSQL", "Kubernetes"],
        experience=[{
            "title": "Backend Engineer",
            "company": "Acme",
            "start": "2020",
            "end": "2024",
            "highlights": "Shipped services with Python and PostgreSQL.",
        }],
        interests=["rock climbing"],
        goals={"narrative": "I want a staff product role", "targetRoles": ["product manager"]},
    )


def _posting(**overrides) -> dict:
    data = {
        "title": "Backend Engineer",
        "company": "Northwind",
        "description": """
Requirements
- Python
- PostgreSQL

Preferred
- Kubernetes
""",
        "skills": "",
    }
    data.update(overrides)
    return extract_requirements(**data)


def test_strong_overlap_scores_high_without_using_goals() -> None:
    evidence = career_evidence(_engineer())
    result = score_fit(evidence, _posting())
    assert result["blockedReason"] is None
    assert result["score"] >= 90
    assert result["titleAlignment"] == 1.0
    assert {item["term"] for item in result["matched"]} >= {"Python", "PostgreSQL", "Kubernetes"}
    assert all(item["source"] == "skill" for item in result["matched"])
    assert result["missing"] == []
    assert title_alignment(evidence, {"title": "Product Manager"}) == 0.0


def test_unrelated_profile_scores_low_and_lists_required_gaps_first() -> None:
    profile = _profile(
        skills=["triage", "patient care"],
        experience=[{"title": "Nurse", "company": "Mercy", "start": "", "end": "", "highlights": "Ran a unit."}],
        interests=["python", "kubernetes"],
        goals={"targetRoles": ["Backend Engineer"], "narrative": "I want to be a backend engineer using python"},
    )
    result = score_fit(career_evidence(profile), _posting())
    assert result["blockedReason"] is None
    assert result["score"] is not None and result["score"] <= 10
    assert result["missing"][:2] == ["Python", "PostgreSQL"]
    assert "Kubernetes" in result["missing"]
    assert result["titleAlignment"] == 0.0


def test_preferred_matches_cannot_hide_missing_required_terms() -> None:
    profile = _profile(
        skills=["Kubernetes"],
        experience=[{"title": "Coordinator", "company": "Acme", "start": "", "end": "", "highlights": "Kept the schedule."}],
    )
    result = score_fit(career_evidence(profile), _posting(title="Designer"))
    assert result["score"] == 20
    assert result["titleAlignment"] == 0.0
    assert result["missing"] == ["Python", "PostgreSQL"]
    assert result["matched"] == [{"term": "Kubernetes", "source": "skill"}]


def test_interests_only_profile_is_blocked_without_a_fake_zero() -> None:
    profile = _profile(
        interests=["python", "kubernetes"],
        goals={"narrative": "I want a backend engineer role", "targetRoles": ["Backend Engineer"]},
    )
    result = score_fit(career_evidence(profile), _posting())
    assert result["score"] is None
    assert result["blockedReason"] == FINISH_ONBOARDING
    assert result["profileBlocked"] is True
    assert result["matched"] == []


def test_missing_job_text_is_blocked_with_the_job_reason() -> None:
    result = score_fit(career_evidence(_engineer()), extract_requirements(title="Backend Engineer", description=""))
    assert result["score"] is None
    assert result["blockedReason"]
    assert result["profileBlocked"] is False
    vague = score_fit(
        career_evidence(_engineer()),
        extract_requirements(title="Backend Engineer", description="We are a great place to work. Join our team and grow your career."),
    )
    assert vague["blockedReason"] == NO_TERMS
    assert vague["score"] is None
