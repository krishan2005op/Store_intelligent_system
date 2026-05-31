from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.db.repositories import EventRepository
from pipeline.schemas import EventIngestResponse, EventIngestResult, RetailEvent


@dataclass(slots=True)
class IngestionService:
    repository: EventRepository

    async def ingest_events(
        self,
        events: list[RetailEvent],
        trace_id: UUID | None = None,
    ) -> EventIngestResponse:
        response_trace_id = trace_id or uuid4()
        seen_in_request: set[UUID] = set()
        unique_candidates: list[RetailEvent] = []
        ordered_results: list[EventIngestResult | None] = []

        for event in events:
            if event.event_id in seen_in_request:
                ordered_results.append(
                    EventIngestResult(
                        event_id=event.event_id,
                        accepted=False,
                        duplicate=True,
                        message="Duplicate event_id in request batch",
                    )
                )
                continue
            seen_in_request.add(event.event_id)
            unique_candidates.append(event)
            ordered_results.append(None)

        existing_ids = await self.repository.existing_event_ids(
            event.event_id for event in unique_candidates
        )
        accepted_events = [
            event for event in unique_candidates if event.event_id not in existing_ids
        ]

        await self.repository.add_events(accepted_events)

        unique_results_by_event_id: dict[UUID, EventIngestResult] = {}
        for event in unique_candidates:
            if event.event_id in existing_ids:
                unique_results_by_event_id[event.event_id] = EventIngestResult(
                    event_id=event.event_id,
                    accepted=False,
                    duplicate=True,
                    message="Event already ingested",
                )
            else:
                unique_results_by_event_id[event.event_id] = EventIngestResult(
                    event_id=event.event_id,
                    accepted=True,
                )

        finalized_results: list[EventIngestResult] = []
        for event, result in zip(events, ordered_results, strict=True):
            finalized_results.append(result or unique_results_by_event_id[event.event_id])

        return EventIngestResponse(
            trace_id=response_trace_id,
            accepted_count=sum(1 for result in finalized_results if result.accepted),
            duplicate_count=sum(1 for result in finalized_results if result.duplicate),
            rejected_count=sum(
                1
                for result in finalized_results
                if not result.accepted and not result.duplicate
            ),
            results=finalized_results,
        )
