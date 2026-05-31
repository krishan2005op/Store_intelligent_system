from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from app.db.repositories import EventRepository
from pipeline.schemas import RetailEvent


class InMemoryEventRepository(EventRepository):
    def __init__(self, initial_events: list[RetailEvent] | None = None) -> None:
        self.events: dict[UUID, RetailEvent] = {}
        for event in initial_events or []:
            self.events[event.event_id] = event

    async def existing_event_ids(self, event_ids: Iterable[UUID]) -> set[UUID]:
        return {event_id for event_id in event_ids if event_id in self.events}

    async def add_events(self, events: list[RetailEvent]) -> None:
        for event in events:
            self.events[event.event_id] = event

    async def latest_event_at(self, store_id: UUID | None = None) -> datetime | None:
        candidates = self.events.values()
        if store_id is not None:
            candidates = [event for event in candidates if event.store_id == store_id]
        timestamps = [event.occurred_at for event in candidates]
        return max(timestamps) if timestamps else None

    async def list_events_for_store(
        self,
        store_id: UUID,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[RetailEvent]:
        events = [event for event in self.events.values() if event.store_id == store_id]
        if start_at is not None:
            events = [event for event in events if event.occurred_at >= start_at]
        if end_at is not None:
            events = [event for event in events if event.occurred_at <= end_at]
        return sorted(events, key=lambda event: (event.occurred_at, event.sequence_number))
