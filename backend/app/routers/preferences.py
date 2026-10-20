from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user
from app.errors import APIError
from app.models import User, UserPreference
from app.schemas import PreferencesResponse, UpdatePreferencesRequest

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


def _response(item: UserPreference) -> PreferencesResponse:
    return PreferencesResponse(dark_mode=item.dark_mode, default_view=item.default_view, interview_rounds=item.interview_rounds)


def _entity(user: User, db: Session) -> UserPreference:
    if user.preferences is not None:
        return user.preferences
    preferences = UserPreference(user_id=user.id)
    db.add(preferences)
    db.commit()
    db.refresh(user)
    return preferences


@router.get("", response_model=PreferencesResponse)
def get_preferences(user: User = Depends(current_user), db: Session = Depends(get_db)) -> PreferencesResponse:
    return _response(_entity(user, db))


@router.put("", response_model=PreferencesResponse)
def update_preferences(body: UpdatePreferencesRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> PreferencesResponse:
    if body.interview_rounds < 1 or body.interview_rounds > 10:
        raise APIError(400, "Interview rounds must be between 1 and 10.")
    preferences = _entity(user, db)
    preferences.dark_mode = body.dark_mode
    preferences.default_view = body.default_view
    preferences.interview_rounds = body.interview_rounds
    db.commit()
    db.refresh(preferences)
    return _response(preferences)
