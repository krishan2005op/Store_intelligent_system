from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.db.repositories import EventRepository
from app.db.session import get_event_repository
from app.services.funnel_schemas import FunnelResponse
from app.services.funnel_service import FunnelService


router = APIRouter(prefix="/stores/{store_id}", tags=["funnel"])


@router.get("/funnel", response_model=FunnelResponse)
async def get_store_funnel(
    store_id: UUID,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    repository: EventRepository = Depends(get_event_repository),
) -> FunnelResponse:
    return await FunnelService(repository).get_store_funnel(store_id, start_at, end_at)
