import json
import uuid

import httpx

from app.config import Settings
from app.models import CareerProfile
from app.services.onboarding import apply_context_update, apply_user_turn, career_context, missing_sections


def _profile() -> CareerProfile:
    return CareerProfile(
        user_id=uuid.uuid4(),
        status="not_started",
        summary="",
        experience=[],
        education=[],
        skills=[],
        interests=[],
        goals={},
        acknowledged={},
        provider="guided",
        notice="",
    )


def test_guided_onboarding_collects_each_section_and_confirms() -> None:
    profile = _profile()
    assert missing_sections(profile) == ["experience", "education", "skills", "interests", "goals"]

    thin = apply_user_turn(profile, "nurse", [])
    assert "more" in thin.reply.lower()
    assert profile.experience == []

    apply_user_turn(profile, "I was a nurse at Mercy from 2019 to 2023. I ran a 12-bed unit.", [])
    assert profile.experience[0]["title"] == "Nurse"
    assert profile.experience[0]["company"] == "Mercy"
    assert profile.experience[0]["start"] == "2019"
    assert profile.experience[0]["end"] == "2023"
    assert "education" in missing_sections(profile)

    apply_user_turn(profile, "none", [])
    assert profile.acknowledged["education"] is True
    assert "education" not in missing_sections(profile)

    apply_user_turn(profile, "patient care, triage, and Epic", [])
    assert profile.skills == ["patient care", "triage", "Epic"]

    apply_user_turn(profile, "teaching, community health", [])
    result = apply_user_turn(profile, "Looking for a clinic manager role, hybrid, around $90k.", [])
    assert missing_sections(profile) == []
    assert result.completed is False
    assert profile.goals["targetRoles"] == ["clinic manager"]
    assert profile.goals["workStyle"] == "hybrid"
    assert profile.goals["compensation"] == "$90k"
    assert "Mercy" in profile.summary

    confirmed = apply_user_turn(profile, "looks good", [])
    assert confirmed.completed is True
    assert "Saved" in confirmed.reply
    context = career_context(profile)
    assert context["missing"] == []
    assert "provider" not in context


def test_none_and_named_section_do_not_block_the_current_question() -> None:
    profile = _profile()
    result = apply_user_turn(profile, "my skills are Python and SQL", [])
    assert profile.skills == ["Python", "SQL"]
    assert "experience" in missing_sections(profile)
    assert "work" in result.reply.lower()
    skipped = apply_user_turn(profile, "no experience", [])
    assert profile.acknowledged["experience"] is True
    assert "education" in skipped.reply.lower()


def test_confirm_is_ignored_until_context_is_complete() -> None:
    profile = _profile()
    result = apply_user_turn(profile, "looks good", [])
    assert result.completed is False
    assert missing_sections(profile) == ["experience", "education", "skills", "interests", "goals"]


def test_model_merges_json_and_keeps_omitted_sections() -> None:
    profile = _profile()
    profile.skills = ["Excel"]
    settings = Settings(ai_endpoint="https://ai.example.test/v1/chat/completions", ai_api_key="secret", auto_migrate=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret"
        body = json.loads(request.content)
        assert body["messages"][-1]["content"] == "I studied at State"
        payload = {
            "reply": "State is in. Which skills should I keep?",
            "education": [{"institution": "State", "credential": "B.S.", "field": "nursing", "notes": "I studied at State"}],
            "skills": [],
            "experience": [{}],
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": f"```json\n{json.dumps(payload)}\n```"}}]})

    result = apply_user_turn(
        profile,
        "I studied at State",
        [("assistant", "What about education?")],
        settings,
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result.provider == "model"
    assert profile.education[0]["institution"] == "State"
    assert profile.skills == ["Excel"]
    assert profile.experience == []


def test_model_failure_falls_back_to_guided_interviewer() -> None:
    profile = _profile()
    settings = Settings(ai_endpoint="https://ai.example.test/v1/chat/completions", auto_migrate=False)
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500, json={"error": "down"})))
    result = apply_user_turn(profile, "I was a nurse at Mercy from 2019 to 2023 in the ICU.", [], settings, client)
    assert result.provider == "guided"
    assert profile.experience[0]["company"] == "Mercy"
    assert "guided interviewer" in result.notice


def test_context_update_replaces_lists_and_reopens_completed_profile() -> None:
    profile = _profile()
    profile.status = "completed"
    profile.skills = ["Excel"]
    profile.interests = ["teaching"]
    profile.experience = [{"title": "nurse", "company": "Mercy", "start": "", "end": "", "highlights": "ICU"}]
    profile.education = [{"institution": "State", "credential": "", "field": "", "year": "", "notes": "State"}]
    profile.goals = {"narrative": "Looking for a clinic manager role", "targetRoles": ["clinic manager"]}
    apply_context_update(profile, skills=["Python"], interests=[])
    assert profile.skills == ["Python"]
    assert profile.interests == []
    assert profile.status == "in_progress"
    assert "interests" in missing_sections(profile)
