SECRET = "a" * 12

POSTING = "Requirements\n- Python\n- PostgreSQL\n\nPreferred\n- Kubernetes"


def _auth(client, email: str) -> dict[str, str]:
    token = client.post("/api/auth/register", json={"email": email, "password": SECRET, "displayName": "Fit"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _save_context(client, headers: dict[str, str], **body) -> None:
    response = client.put("/api/onboarding/context", headers=headers, json=body)
    assert response.status_code == 200


def test_saved_job_fit_is_owner_scoped_and_blocks_honestly(client) -> None:
    headers = _auth(client, "fit@example.com")
    created = client.post("/api/jobs", headers=headers, json={
        "company": "Northwind",
        "title": "Backend Engineer",
        "status": "Applied",
        "description": POSTING,
    })
    job_id = created.json()["id"]

    blocked = client.get(f"/api/jobs/{job_id}/fit", headers=headers)
    assert blocked.status_code == 200
    assert blocked.json()["score"] is None
    assert blocked.json()["profileBlocked"] is True
    assert blocked.json()["blockedReason"] == "Finish onboarding."

    _save_context(
        client,
        headers,
        skills=["Python", "PostgreSQL", "Kubernetes"],
        experience=[{"title": "Backend Engineer", "company": "Acme", "start": "2020", "end": "2024", "highlights": "Python services"}],
    )
    fitted = client.get(f"/api/jobs/{job_id}/fit", headers=headers)
    assert fitted.status_code == 200
    body = fitted.json()
    assert body["score"] >= 90
    assert body["blockedReason"] is None
    assert body["titleAlignment"] == 1.0

    empty = client.put(f"/api/jobs/{job_id}", headers=headers, json={
        "company": "Northwind",
        "title": "Backend Engineer",
        "status": "Applied",
        "description": "",
        "skills": "",
    })
    assert empty.status_code == 200
    missing = client.get(f"/api/jobs/{job_id}/fit", headers=headers)
    assert missing.json()["score"] is None
    assert missing.json()["profileBlocked"] is False
    assert missing.json()["blockedReason"] == "The posting has no usable text."

    other = _auth(client, "other-fit@example.com")
    assert client.get(f"/api/jobs/{job_id}/fit", headers=other).status_code == 404


def test_pasted_posting_uses_the_same_score(client) -> None:
    headers = _auth(client, "preview-fit@example.com")
    _save_context(
        client,
        headers,
        skills=["Python"],
        experience=[{"title": "Analyst", "company": "Acme", "start": "", "end": "", "highlights": "Reports"}],
        interests=["kubernetes"],
    )
    response = client.post("/api/jobs/fit", headers=headers, json={
        "title": "Designer",
        "company": "Northwind",
        "description": "Requirements\n- Python\n\nPreferred\n- Kubernetes",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 70
    assert body["missing"] == ["Kubernetes"]
    assert body["matched"][0]["source"] == "skill"
