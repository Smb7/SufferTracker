from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
import httpx

from app.deps import current_user
from app.errors import APIError
from app.models import User
from app.schemas import ParsedJobResponse
from app.services.images import MAX_IMAGE_BYTES, SUPPORTED, has_image_signature
from app.services.ocr import extract_text
from app.services.parser import parse_screenshot, parse_text, parse_url
from app.services.url_guard import UrlGuardError, validate_public_http_url

router = APIRouter(prefix="/api/jobs/parse", tags=["parsing"])
PAGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@router.get("/fetch-page")
def fetch_page(url: str = Query(...), _: User = Depends(current_user)) -> Response:
    try:
        target = validate_public_http_url(url)
        with httpx.Client(timeout=20, follow_redirects=True, headers=PAGE_HEADERS) as client:
            response = client.get(target)
            response.raise_for_status()
        media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if media_type and not media_type.startswith("text/") and media_type != "application/xhtml+xml":
            raise APIError(400, "That URL is not an HTML page.")
        return HTMLResponse(response.text)
    except UrlGuardError as exc:
        raise APIError(400, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise APIError(400, f"Could not fetch URL: {exc}") from exc


@router.post("", response_model=ParsedJobResponse)
async def parse(
    inputType: str = Form(...),
    text: str | None = Form(None),
    url: str | None = Form(None),
    image: UploadFile | None = File(None),
    _: User = Depends(current_user),
) -> ParsedJobResponse:
    try:
        if inputType == "Text":
            return parse_text(text or "")
        if inputType == "Link":
            return parse_url(url or "")
        if inputType != "Screenshot":
            raise APIError(400, "Unsupported input type.")
        if image is None:
            raise APIError(400, "An image is required for screenshot parsing.")
        data = await image.read()
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise APIError(400, "Screenshot must be between 1 byte and 10 MB.")
        content_type = image.content_type or ""
        if content_type.lower() not in SUPPORTED:
            raise APIError(400, "Only JPEG, PNG, and WebP screenshots are supported.")
        if not has_image_signature(data, content_type):
            raise APIError(400, "The uploaded file does not match its declared image type.")
        return parse_screenshot(data, image.filename or "screenshot", content_type)
    except UrlGuardError as exc:
        raise APIError(400, str(exc)) from exc
    except ValueError as exc:
        raise APIError(400, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise APIError(400, f"Could not fetch URL: {exc}") from exc
