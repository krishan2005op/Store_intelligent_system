from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.db.repositories import EventRepository
from app.db.session import get_event_repository
from app.services.metrics_schemas import HeatmapResponse, StoreMetricsResponse
from app.services.metrics_service import MetricsService


router = APIRouter(prefix="/stores/{store_id}", tags=["metrics"])


@router.get("/metrics", response_model=StoreMetricsResponse)
async def get_store_metrics(
    store_id: UUID,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    repository: EventRepository = Depends(get_event_repository),
) -> StoreMetricsResponse:
    return await MetricsService(repository).get_store_metrics(store_id, start_at, end_at)


@router.get("/heatmap", response_model=HeatmapResponse)
async def get_store_heatmap(
    store_id: UUID,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    repository: EventRepository = Depends(get_event_repository),
) -> HeatmapResponse:
    return await MetricsService(repository).get_heatmap(store_id, start_at, end_at)
