from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger
from app.core.config import AppSettings, get_settings
from app.db.repositories import EventRepository
from app.db.session import get_event_repository


router = APIRouter(tags=["health"])
logger = get_logger(__name__)


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    app_name: str
    environment: str
    pipeline_mode: str
    latest_event_at: datetime | None
    feed_stale: bool
    database_connected: bool


@router.get("/health", response_model=HealthResponse)
async def health_check(
    settings: AppSettings = Depends(get_settings),
    repository: EventRepository = Depends(get_event_repository),
) -> HealthResponse:
    database_connected = True
    latest_event_at: datetime | None = None
    try:
        latest_event_at = await repository.latest_event_at()
    except (OSError, SQLAlchemyError) as exc:
        database_connected = False
        logger.warning(
            "health_dependency_unavailable",
            dependency="postgres",
            error_type=type(exc).__name__,
        )

    feed_stale = False
    if latest_event_at is not None:
        age_seconds = (datetime.now(UTC) - latest_event_at).total_seconds()
        feed_stale = age_seconds > settings.event_stale_after_seconds

    return HealthResponse(
        status="ok" if database_connected else "degraded",
        app_name=settings.app_name,
        environment=settings.environment,
        pipeline_mode=settings.pipeline_mode,
        latest_event_at=latest_event_at,
        feed_stale=feed_stale,
        database_connected=database_connected,
    )
