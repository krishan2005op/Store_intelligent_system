from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.db.repositories import EventRepository
from app.db.session import get_event_repository
from app.services.anomaly_schemas import AnomalyResponse
from app.services.anomaly_service import AnomalyService


router = APIRouter(prefix="/stores/{store_id}", tags=["anomalies"])


@router.get("/anomalies", response_model=AnomalyResponse)
async def get_store_anomalies(
    store_id: UUID,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    repository: EventRepository = Depends(get_event_repository),
) -> AnomalyResponse:
    return await AnomalyService(repository).get_store_anomalies(store_id, start_at, end_at)
