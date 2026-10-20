SECRET = "a" * 12


def _headers(client) -> dict[str, str]:
    token = client.post("/api/auth/register", json={"email": "jobs@example.com", "password": SECRET, "displayName": "Jobs"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_job_crud_keeps_timeline_and_owner_scope(client) -> None:
    headers = _headers(client)
    created = client.post("/api/jobs", headers=headers, json={
        "company": "Acme", "title": "Engineer", "status": "Interview", "interviewRound": 2,
        "timeline": ["Applied", "Interview", "Interview"], "description": "Build things",
    })
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "Interview"
    assert body["interviewRound"] == 2
    assert body["timeline"] == ["Applied", "Interview", "Interview"]
    job_id = body["id"]

    listed = client.get("/api/jobs", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == job_id

    offer = client.put(f"/api/jobs/{job_id}", headers=headers, json={
        "company": "Acme", "title": "Engineer", "status": "JobOffer", "timeline": ["Applied", "JobOffer"],
    })
    assert offer.status_code == 400

    saved = client.put(f"/api/jobs/{job_id}", headers=headers, json={
        "company": "Acme Labs", "title": "Staff Engineer", "status": "JobOffer",
        "timeline": ["Applied", "Interview", "JobOffer"],
    })
    assert saved.status_code == 200
    assert saved.json()["company"] == "Acme Labs"
    assert saved.json()["status"] == "JobOffer"

    other = client.post("/api/auth/register", json={"email": "other-jobs@example.com", "password": SECRET, "displayName": "Other"}).json()["token"]
    assert client.get(f"/api/jobs/{job_id}", headers={"Authorization": f"Bearer {other}"}).status_code == 404
    assert client.delete(f"/api/jobs/{job_id}", headers=headers).status_code == 204
    assert client.get("/api/jobs", headers=headers).json() == []


def test_create_rejects_interview_without_round(client) -> None:
    headers = _headers(client)
    response = client.post("/api/jobs", headers=headers, json={"company": "Acme", "title": "Engineer", "status": "Interview"})
    assert response.status_code == 400
    assert "round" in response.json()["message"]
