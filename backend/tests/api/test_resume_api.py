import json

from sqlalchemy import func, select

from app.models import TailoredResume

SECRET = "a" * 12
POSTING = "Requirements\n- Python\n- PostgreSQL\n\nPreferred\n- Kubernetes"
NO_TERMS = "We are a great place to work. Join our team and grow your career."


def _auth(client, email: str) -> dict[str, str]:
    token = client.post("/api/auth/register", json={"email": email, "password": SECRET, "displayName": "Resume"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _save_context(client, headers: dict[str, str]) -> None:
    response = client.put("/api/onboarding/context", headers=headers, json={
        "skills": ["Python", "PostgreSQL"],
        "experience": [{
            "title": "Backend Engineer",
            "company": "Acme",
            "start": "2020",
            "end": "2024",
            "highlights": "Shipped services with Python and PostgreSQL.",
        }],
        "education": [{"institution": "State", "credential": "B.S.", "field": "Computer Science", "year": "2018", "notes": ""}],
        "interests": ["rock climbing"],
        "goals": {"narrative": "I want a staff role at Initech", "targetRoles": ["chief medical officer"]},
    })
    assert response.status_code == 200


def _job(client, headers: dict[str, str], description: str = POSTING) -> str:
    created = client.post("/api/jobs", headers=headers, json={
        "company": "Northwind",
        "title": "Backend Engineer",
        "status": "Applied",
        "description": description,
    })
    assert created.status_code == 201
    return created.json()["id"]


def test_blocked_resume_matches_fit_and_creates_no_row(client, db) -> None:
    headers = _auth(client, "resume-blocked@example.com")
    job_id = _job(client, headers)
    blocked = client.post(f"/api/jobs/{job_id}/resume", headers=headers)
    assert blocked.status_code == 200
    assert blocked.json()["score"] is None
    assert blocked.json()["profileBlocked"] is True
    assert blocked.json()["blockedReason"] == "Finish onboarding."
    assert blocked.json()["sections"] is None
    assert db.scalar(select(func.count()).select_from(TailoredResume)) == 0

    _save_context(client, headers)
    client.put(f"/api/jobs/{job_id}", headers=headers, json={
        "company": "Northwind",
        "title": "Backend Engineer",
        "status": "Applied",
        "description": "",
        "skills": "",
    })
    empty = client.post(f"/api/jobs/{job_id}/resume", headers=headers)
    assert empty.json()["blockedReason"] == "The posting has no usable text."
    assert empty.json()["profileBlocked"] is False
    assert db.scalar(select(func.count()).select_from(TailoredResume)) == 0

    client.put(f"/api/jobs/{job_id}", headers=headers, json={
        "company": "Northwind",
        "title": "Backend Engineer",
        "status": "Applied",
        "description": NO_TERMS,
        "skills": "",
    })
    termless = client.post(f"/api/jobs/{job_id}/resume", headers=headers)
    assert termless.json()["blockedReason"] == "The posting has no usable terms."
    assert db.scalar(select(func.count()).select_from(TailoredResume)) == 0
    assert client.get(f"/api/jobs/{job_id}/resume", headers=headers).status_code == 404


def test_guided_resume_is_owner_scoped_and_edits_stay_cited(client, db) -> None:
    headers = _auth(client, "resume-guided@example.com")
    _save_context(client, headers)
    job_id = _job(client, headers)
    drafted = client.post(f"/api/jobs/{job_id}/resume", headers=headers)
    assert drafted.status_code == 200
    body = drafted.json()
    assert body["score"] is not None
    assert body["updatedAtUtc"]
    assert "updatedAt" not in body
    assert body["blockedReason"] is None
    assert "Python" in json.dumps(body["sections"])
    assert "Initech" not in json.dumps(body)
    assert "rock climbing" not in json.dumps(body)
    assert body["sections"]["education"][0]["credential"] == "B.S."
    assert db.scalar(select(func.count()).select_from(TailoredResume)) == 1

    again = client.post(f"/api/jobs/{job_id}/resume", headers=headers)
    assert again.status_code == 200
    assert db.scalar(select(func.count()).select_from(TailoredResume)) == 1

    other = _auth(client, "resume-other@example.com")
    assert client.get(f"/api/jobs/{job_id}/resume", headers=other).status_code == 404
    assert client.post(f"/api/jobs/{job_id}/resume", headers=other).status_code == 404

    sections = body["sections"]
    sections["experience"][0]["bullets"][0]["text"] = "Delivered services with Python and PostgreSQL."
    saved = client.put(f"/api/jobs/{job_id}/resume", headers=headers, json={"sections": sections})
    assert saved.status_code == 200
    assert saved.json()["sections"]["experience"][0]["bullets"][0]["text"].startswith("Delivered")

    sections["experience"][0]["bullets"][0]["text"] = "Built Python services at Initech."
    rejected = client.put(f"/api/jobs/{job_id}/resume", headers=headers, json={"sections": sections})
    assert rejected.status_code == 400
    assert "employer" in rejected.json()["message"]
    kept = client.get(f"/api/jobs/{job_id}/resume", headers=headers)
    assert "Initech" not in json.dumps(kept.json())
    assert kept.json()["sections"]["experience"][0]["bullets"][0]["text"].startswith("Delivered")

    sections["experience"][0]["bullets"][0]["text"] = "Delivered services with Python and PostgreSQL."
    sections["experience"][0]["company"] = "Initech"
    moved = client.put(f"/api/jobs/{job_id}/resume", headers=headers, json={"sections": sections})
    assert moved.status_code == 400
    assert client.get(f"/api/jobs/{job_id}/resume", headers=headers).json()["sections"]["experience"][0]["company"] == "Acme"


def test_model_fake_employer_is_not_saved(client, monkeypatch) -> None:
    from app.config import Settings
    from app.services.ai import ChatResult

    headers = _auth(client, "resume-model@example.com")
    _save_context(client, headers)
    job_id = _job(client, headers)
    preview = client.post(f"/api/jobs/{job_id}/resume", headers=headers).json()
    bullet_id = preview["sections"]["experience"][0]["bullets"][0]["evidenceId"]
    monkeypatch.setattr(
        "app.routers.jobs.get_settings",
        lambda: Settings(ai_endpoint="https://ai.example.test/v1/chat/completions", auto_migrate=False, jwt_key="x"),
    )

    def fake(messages, settings=None, client=None):
        assert "Evidence JSON" in messages[0]["content"]
        assert "missing" in messages[0]["content"].lower() or "Fit JSON" in messages[0]["content"]
        return ChatResult(json.dumps({
            "summary": "Engineer at Initech",
            "experience": [{"roleId": 0, "bullets": [{"evidenceId": bullet_id, "text": "Built Python services at Initech."}]}],
        }), True)

    monkeypatch.setattr("app.services.resume.complete_chat", fake)
    drafted = client.post(f"/api/jobs/{job_id}/resume", headers=headers)
    assert drafted.status_code == 200
    assert "Initech" not in json.dumps(drafted.json())
    assert "Python" in drafted.json()["sections"]["experience"][0]["bullets"][0]["text"]


def test_delete_job_or_account_removes_resume(client, db) -> None:
    headers = _auth(client, "resume-delete@example.com")
    _save_context(client, headers)
    job_id = _job(client, headers)
    assert client.post(f"/api/jobs/{job_id}/resume", headers=headers).status_code == 200
    assert db.scalar(select(func.count()).select_from(TailoredResume)) == 1
    assert client.delete(f"/api/jobs/{job_id}", headers=headers).status_code == 204
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(TailoredResume)) == 0

    other_job = _job(client, headers)
    assert client.post(f"/api/jobs/{other_job}/resume", headers=headers).status_code == 200
    assert client.delete("/api/auth/account", headers=headers).status_code == 204
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(TailoredResume)) == 0
