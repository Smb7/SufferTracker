import uuid

from app.models import CareerProfile
from app.services.evidence import career_evidence, normalize_key, source_for


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


def _keys(evidence: dict, bucket: str) -> set[str]:
    return {item["key"] for item in evidence[bucket]}


def test_narrative_highlights_yield_tools_without_shredding_the_sentence() -> None:
    profile = _profile(
        experience=[{
            "title": "Clinic coordinator",
            "company": "Mercy Health",
            "start": "2019",
            "end": "2023",
            "highlights": "Built internal tools with Python and PostgreSQL for the clinic intake team. Coordinated schedules in Epic.",
        }],
        education=[{
            "institution": "State University",
            "credential": "B.S.",
            "field": "Public Health",
            "year": "2018",
            "notes": "Capstone on community clinics and python workshops.",
        }],
        skills=["patient care", "triage"],
        interests=["teaching", "community health"],
        goals={"narrative": "I want a product role that uses python someday", "targetRoles": ["product manager"]},
    )
    evidence = career_evidence(profile)
    experience = _keys(evidence, "experienceTerms")
    assert "python" in experience
    assert "postgresql" in experience
    assert "epic" in experience
    assert "clinic coordinator" in experience
    assert "mercy health" in experience
    assert "built" not in experience
    assert "internal" not in experience
    assert "intake" not in experience
    assert "schedules" not in experience
    assert "team" not in experience

    assert evidence["roles"] == [{
        "id": 0,
        "title": "Clinic coordinator",
        "company": "Mercy Health",
        "start": "2019",
        "end": "2023",
        "highlights": "Built internal tools with Python and PostgreSQL for the clinic intake team. Coordinated schedules in Epic.",
    }]
    assert _keys(evidence, "skills") == {"patient care", "triage"}
    assert "patient" not in _keys(evidence, "skills")
    assert normalize_key("B.S.") in _keys(evidence, "educationTerms")
    assert "public health" in _keys(evidence, "educationTerms")
    assert "state university" in _keys(evidence, "educationTerms")
    assert "python" not in _keys(evidence, "educationTerms")

    assert source_for(evidence, "Python") == "experience"
    assert source_for(evidence, "triage") == "skill"
    assert source_for(evidence, "Public Health") == "education"
    assert source_for(evidence, "product manager") is None
    assert source_for(evidence, "teaching") is None
    assert "product manager" not in experience
    assert "teaching" not in experience
    assert evidence["targeting"]["interests"] == ["teaching", "community health"]
    assert evidence["targeting"]["targetRoles"] == ["product manager"]
    assert "python" in evidence["targeting"]["narrative"]


def test_interests_only_profile_has_no_evidence_terms() -> None:
    profile = _profile(
        interests=["rock climbing", "clinic design", "python"],
        goals={
            "narrative": "I love python and want a clinic design role",
            "targetRoles": ["clinic designer"],
            "workStyle": "remote",
        },
    )
    evidence = career_evidence(profile)
    assert evidence["skills"] == []
    assert evidence["experienceTerms"] == []
    assert evidence["educationTerms"] == []
    assert evidence["roles"] == []
    assert source_for(evidence, "python") is None
    assert source_for(evidence, "clinic design") is None
    assert source_for(evidence, "clinic designer") is None
    assert evidence["targeting"]["interests"] == ["rock climbing", "clinic design", "python"]
    assert evidence["targeting"]["narrative"].startswith("I love python")


def test_short_highlight_list_splits_on_commas_and_and() -> None:
    profile = _profile(experience=[{
        "title": "Analyst",
        "company": "Northwind",
        "start": "",
        "end": "",
        "highlights": "Python, SQL, and Epic",
    }])
    evidence = career_evidence(profile)
    assert {"python", "sql", "epic"} <= _keys(evidence, "experienceTerms")
    assert source_for(evidence, "sql") == "experience"


def test_sentence_and_is_not_two_fake_skills() -> None:
    profile = _profile(experience=[{
        "title": "Nurse",
        "company": "Mercy",
        "start": "",
        "end": "",
        "highlights": "I led the night shift and trained new nurses.",
    }])
    evidence = career_evidence(profile)
    keys = _keys(evidence, "experienceTerms")
    assert "nurse" in keys
    assert "led the night shift" not in keys
    assert "trained new nurses" not in keys
    assert "shift" not in keys
    assert "trained" not in keys


def test_duplicate_terms_keep_one_display_and_skill_wins_source() -> None:
    profile = _profile(
        skills=["Python", "python", "C#"],
        experience=[{
            "title": "Engineer",
            "company": "Acme",
            "start": "",
            "end": "",
            "highlights": "Shipped services with Python and C#.",
        }],
    )
    evidence = career_evidence(profile)
    python = [item for item in evidence["skills"] if item["key"] == "python"]
    assert len(python) == 1
    assert python[0]["display"] == "Python"
    assert any(item["key"] == "c#" for item in evidence["skills"])
    assert source_for(evidence, "C#") == "skill"
    assert source_for(evidence, "python") == "skill"
