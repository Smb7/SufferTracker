from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import current_user
from app.errors import APIError
from app.models import User
from app.schemas import (
    OpenCodeConnectRequest,
    OpenCodeModelRequest,
    OpenCodeModelResponse,
    OpenCodeStatusResponse,
    OpenCodeTestResponse,
)
from app.services.ai import AiProviderError
from app.services.opencode import (
    OpenCodeError,
    TEST_PROMPT,
    clean_api_key,
    complete_opencode,
    connection_for,
    ensure_available,
    list_models,
    mark_check,
    require_model,
    save_connection,
    stored_key,
    verify_key,
)

router = APIRouter(prefix="/api/integrations/opencode", tags=["opencode"])


def _status(user: User, db: Session) -> OpenCodeStatusResponse:
    settings = get_settings()
    row = connection_for(user, db)
    if row is not None:
        return OpenCodeStatusResponse(
            configured=True,
            key_hint=row.key_hint,
            model_id=row.model_id,
            source="opencode",
            last_checked_at=row.last_checked_at,
            last_error=row.last_error,
        )
    if settings.ai_endpoint:
        return OpenCodeStatusResponse(configured=False, source="environment")
    return OpenCodeStatusResponse(configured=False, source="none")


def _guard(exc: OpenCodeError) -> APIError:
    return APIError(exc.status_code, exc.message)


@router.get("", response_model=OpenCodeStatusResponse)
def get_opencode(user: User = Depends(current_user), db: Session = Depends(get_db)) -> OpenCodeStatusResponse:
    return _status(user, db)


@router.get("/models", response_model=list[OpenCodeModelResponse])
def get_models(_user: User = Depends(current_user)) -> list[OpenCodeModelResponse]:
    return [OpenCodeModelResponse.model_validate(item) for item in list_models()]


@router.put("", response_model=OpenCodeStatusResponse)
def connect_opencode(
    body: OpenCodeConnectRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> OpenCodeStatusResponse:
    try:
        model_id = require_model(body.model_id)
        row = connection_for(user, db)
        settings = get_settings()
        if body.api_key.strip():
            api_key = clean_api_key(body.api_key)
        elif row is None:
            raise OpenCodeError("An API key is required.", 400)
        else:
            api_key = stored_key(row, settings)
        ensure_available(model_id, verify_key(api_key))
        save_connection(db, user, api_key, model_id, settings)
    except OpenCodeError as exc:
        raise _guard(exc) from exc
    return _status(user, db)


@router.patch("", response_model=OpenCodeStatusResponse)
def update_opencode_model(
    body: OpenCodeModelRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> OpenCodeStatusResponse:
    row = connection_for(user, db)
    if row is None:
        raise APIError(404, "Connect OpenCode before choosing a model.")
    try:
        row.model_id = require_model(body.model_id)
    except OpenCodeError as exc:
        raise _guard(exc) from exc
    db.commit()
    db.refresh(row)
    return _status(user, db)


@router.post("/test", response_model=OpenCodeTestResponse)
def test_opencode(user: User = Depends(current_user), db: Session = Depends(get_db)) -> OpenCodeTestResponse:
    row = connection_for(user, db)
    if row is None:
        raise APIError(404, "Connect OpenCode before testing it.")
    settings = get_settings()
    try:
        api_key = stored_key(row, settings)
        complete_opencode([{"role": "user", "content": TEST_PROMPT}], row.model_id, api_key)
    except OpenCodeError as exc:
        mark_check(db, row, exc.message)
        return OpenCodeTestResponse(ok=False, message=exc.message)
    except AiProviderError as exc:
        mark_check(db, row, str(exc))
        return OpenCodeTestResponse(ok=False, message=str(exc))
    mark_check(db, row, "")
    return OpenCodeTestResponse(ok=True, message="OpenCode replied.")


@router.delete("", status_code=204)
def disconnect_opencode(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    row = connection_for(user, db)
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=204)
