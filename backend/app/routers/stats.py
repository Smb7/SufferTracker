from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import JobApplication
from app.schemas import PublicStatsResponse
from app.services.stats import week_start

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/public", response_model=PublicStatsResponse)
def public_stats(db: Session = Depends(get_db)) -> PublicStatsResponse:
    start = week_start(datetime.now(timezone.utc))
    count = db.scalar(select(func.count()).select_from(JobApplication).where(JobApplication.applied_at >= start)) or 0
    return PublicStatsResponse(applications_this_week=count)
