SECRET = "a" * 12
PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


def _headers(client) -> dict[str, str]:
    token = client.post("/api/auth/register", json={"email": "parse@example.com", "password": SECRET, "displayName": "Parse"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_parse_rejects_png_with_invalid_signature(client) -> None:
    headers = _headers(client)
    response = client.post("/api/jobs/parse", headers=headers, data={"inputType": "Screenshot"}, files={"image": ("posting.png", b"\x01\x02\x03", "image/png")})
    assert response.status_code == 400
    assert "image type" in response.json()["message"]


def test_parse_forwards_valid_png_to_pending_ocr(client) -> None:
    headers = _headers(client)
    response = client.post("/api/jobs/parse", headers=headers, data={"inputType": "Screenshot"}, files={"image": ("posting.png", PNG, "image/png")})
    assert response.status_code == 200
    assert response.json()["company"] == "OCR pending"


def test_parse_text_endpoint(client) -> None:
    headers = _headers(client)
    response = client.post("/api/jobs/parse", headers=headers, data={"inputType": "Text", "text": "Company: Acme\nTitle: Engineer\nLocation: Remote"})
    assert response.status_code == 200
    assert response.json()["company"] == "Acme"
    assert response.json()["title"] == "Engineer"
