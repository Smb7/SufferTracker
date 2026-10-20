import logging
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrResult:
    text: str
    provider_used: bool
    notice: str


def extract_text(image: bytes, file_name: str, content_type: str, settings: Settings | None = None, client: httpx.Client | None = None) -> OcrResult:
    settings = settings or get_settings()
    if not settings.ocr_endpoint:
        logger.info("OCR requested for %s; endpoint is not configured.", file_name)
        return OcrResult("", False, "OCR provider is not configured. Add Ocr:Endpoint to enable screenshot extraction.")
    owns_client = client is None
    http = client or httpx.Client(timeout=30)
    try:
        headers = {}
        if settings.ocr_api_key:
            headers[settings.ocr_api_key_header or "Ocp-Apim-Subscription-Key"] = settings.ocr_api_key
        response = http.post(settings.ocr_endpoint, files={"image": (file_name, image, content_type)}, headers=headers)
        response.raise_for_status()
        text = _read_text(response.json())
        if not text or not text.strip():
            raise ValueError("The OCR provider returned no readable text.")
        return OcrResult(text.strip(), True, "OCR extracted these details. Review them before saving.")
    finally:
        if owns_client:
            http.close()


def _read_text(root: object) -> str | None:
    if isinstance(root, str):
        return root
    if not isinstance(root, dict):
        return None
    for key in ("text", "content", "fullText"):
        value = root.get(key)
        if isinstance(value, str):
            return value
    if "analyzeResult" in root:
        return _read_azure(root["analyzeResult"])
    if "readResult" in root:
        return _read_azure(root["readResult"])
    return None


def _read_azure(root: object) -> str | None:
    if not isinstance(root, dict) or not isinstance(root.get("readResults"), list):
        return None
    lines = []
    for page in root["readResults"]:
        if not isinstance(page, dict):
            continue
        for line in page.get("lines") or []:
            if isinstance(line, dict) and line.get("text"):
                lines.append(str(line["text"]))
    return "\n".join(lines) if lines else None
