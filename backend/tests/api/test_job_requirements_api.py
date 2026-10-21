SECRET = "a" * 12


def _headers(client, email: str) -> dict[str, str]:
    token = client.post("/api/auth/register", json={"email": email, "password": SECRET, "displayName": "Jobs"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_requirements_recompute_for_the_owner_only(client) -> None:
    headers = _headers(client, "requirements@example.com")
    created = client.post("/api/jobs", headers=headers, json={
        "company": "Mercy Health",
        "title": "Clinic Manager",
        "status": "Applied",
        "description": "Qualifications\n- RN license\n- clinic scheduling\n\nPreferred\n- Spanish",
        "skills": "Epic",
    })
    assert created.status_code == 201
    job_id = created.json()["id"]

    first = client.get(f"/api/jobs/{job_id}/requirements", headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert body["blockedReason"] is None
    assert "RN license" in body["required"]
    assert "Spanish" in body["preferred"]
    assert "Epic" in body["keywords"]

    updated = client.put(f"/api/jobs/{job_id}", headers=headers, json={
        "company": "Mercy Health",
        "title": "Clinic Manager",
        "status": "Applied",
        "description": "We are a great place to work. Join our team and grow your career.",
        "skills": "",
    })
    assert updated.status_code == 200
    again = client.get(f"/api/jobs/{job_id}/requirements", headers=headers)
    assert again.json()["blockedReason"] == "The posting has no usable terms."
    assert again.json()["keywords"] == []

    other = _headers(client, "other-requirements@example.com")
    assert client.get(f"/api/jobs/{job_id}/requirements", headers=other).status_code == 404
