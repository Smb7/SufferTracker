import httpx

from app.config import Settings
from app.services.ocr import extract_text


def test_extract_text_reads_provider_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Ocp-Apim-Subscription-Key"] == "test-key"
        return httpx.Response(200, json={"text": "Senior Engineer\nCompany: Acme"})

    result = extract_text(b"\x01\x02", "posting.png", "image/png", Settings(ocr_endpoint="https://ocr.example.test/read", ocr_api_key="test-key", auto_migrate=False), httpx.Client(transport=httpx.MockTransport(handler)))
    assert result.provider_used is True
    assert result.text == "Senior Engineer\nCompany: Acme"


def test_extract_text_pending_without_endpoint() -> None:
    result = extract_text(b"\x01\x02", "posting.png", "image/png", Settings(ocr_endpoint="", auto_migrate=False))
    assert result.provider_used is False
    assert "not configured" in result.notice
