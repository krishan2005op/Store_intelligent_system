from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from app.db.repositories import EventRepository
from app.db.session import get_event_repository
from app.services.ingestion_service import IngestionService
from pipeline.schemas import EventIngestRequest, EventIngestResponse


router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "/ingest",
    response_model=EventIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_events(
    payload: EventIngestRequest,
    request: Request,
    repository: EventRepository = Depends(get_event_repository),
    x_trace_id: UUID | None = Header(default=None, alias="X-Trace-Id"),
) -> EventIngestResponse:
    trace_id = x_trace_id or getattr(request.state, "trace_id", None)
    service = IngestionService(repository)
    return await service.ingest_events(payload.events, trace_id=trace_id)
