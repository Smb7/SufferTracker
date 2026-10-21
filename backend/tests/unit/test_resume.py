import json
import uuid

import httpx
import pytest

from app.config import Settings
from app.models import CareerProfile
from app.services.evidence import career_evidence
from app.services.requirements import extract_requirements
from app.services.resume import EDIT_REJECTED, ResumeEditError, accept_edits, generate_resume

POSTING = "Requirements\n- Python\n- PostgreSQL\n\nPreferred\n- Kubernetes"


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
        skills=["Excel", "Python", "PostgreSQL"],
        experience=[{
            "title": "Backend Engineer",
            "company": "Acme",
            "start": "2020",
            "end": "2024",
            "highlights": "Shipped services with Python and PostgreSQL.",
        }],
        education=[{
            "institution": "State",
            "credential": "B.S.",
            "field": "Computer Science",
            "year": "2018",
            "notes": "",
        }],
        interests=["rock climbing"],
        goals={"narrative": "I want a staff role at Initech", "targetRoles": ["chief medical officer"]},
    )


def test_guided_resume_orders_matches_and_skips_targeting() -> None:
    profile = _engineer()
    evidence = career_evidence(profile)
    result = generate_resume(
        evidence,
        extract_requirements("Backend Engineer", "Northwind", POSTING, ""),
        education=profile.education,
        settings=Settings(ai_endpoint="", auto_migrate=False),
    )
    assert result["blockedReason"] is None
    assert result["score"] is not None
    assert result["missing"] == ["Kubernetes"]
    skills = [item["text"] for item in result["sections"]["skills"]]
    assert skills[0] == "Python"
    assert "Excel" in skills
    blob = json.dumps(result["sections"])
    assert "rock climbing" not in blob
    assert "Initech" not in blob
    assert "chief medical" not in blob.casefold()
    assert "Kubernetes" not in blob
    assert "B.S." in blob
    assert "PhD" not in blob
    role = result["sections"]["experience"][0]
    assert role["company"] == "Acme"
    assert "Python" in role["bullets"][0]["text"]
    assert result["evidenceIds"]


def test_model_fake_employer_is_stripped() -> None:
    profile = _engineer()
    evidence = career_evidence(profile)
    bullet_id = next(item["id"] for item in evidence["experienceTerms"] if item["field"] == "highlights")
    skill_id = evidence["skills"][0]["id"]
    education_id = next(item["id"] for item in evidence["educationTerms"] if item["field"] == "credential")
    payload = {
        "summary": "Senior engineer at Initech",
        "skills": [{"evidenceId": skill_id, "text": "Python, sold by Initech"}],
        "experience": [{
            "roleId": 0,
            "bullets": [{"evidenceId": bullet_id, "text": "Built Python services at Initech."}],
        }],
        "education": [{"evidenceId": education_id, "text": "PhD at Initech"}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        assert body["messages"][0]["role"] == "system"
        assert "Evidence JSON" in system
        assert "Do not add employers" in system
        assert "Initech" not in system
        fenced = "```json\n" + json.dumps(payload) + "\n```"
        return httpx.Response(200, json={"choices": [{"message": {"content": fenced}}]})

    result = generate_resume(
        evidence,
        extract_requirements("Backend Engineer", "Northwind", POSTING, ""),
        education=profile.education,
        settings=Settings(ai_endpoint="https://ai.example.test/v1/chat/completions", ai_model="test", auto_migrate=False),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    blob = json.dumps(result)
    assert "Initech" not in blob
    assert "PhD" not in blob
    assert "Shipped services with Python and PostgreSQL." in blob
    assert result["sections"]["skills"][0]["text"] != "Python, sold by Initech"
    assert "B.S." in result["sections"]["education"][0]["text"]


def test_save_rejects_a_new_employer_and_keeps_wording() -> None:
    profile = _engineer()
    evidence = career_evidence(profile)
    drafted = generate_resume(
        evidence,
        extract_requirements("Backend Engineer", "Northwind", POSTING, ""),
        education=profile.education,
        settings=Settings(ai_endpoint="", auto_migrate=False),
    )
    sections = drafted["sections"]
    edited = json.loads(json.dumps(sections))
    edited["experience"][0]["bullets"][0]["text"] = "Delivered services with Python and PostgreSQL."
    saved = accept_edits(edited, evidence, profile.education)
    assert saved["experience"][0]["bullets"][0]["text"] == "Delivered services with Python and PostgreSQL."

    edited["experience"][0]["bullets"][0]["text"] = "Built Python services at Initech."
    with pytest.raises(ResumeEditError, match=EDIT_REJECTED):
        accept_edits(edited, evidence, profile.education)
    edited["experience"][0]["bullets"][0]["text"] = "Delivered services with Python and PostgreSQL."
    edited["education"][0]["text"] = "PhD, Computer Science, State, 2018"
    with pytest.raises(ResumeEditError, match=EDIT_REJECTED):
        accept_edits(edited, evidence, profile.education)
