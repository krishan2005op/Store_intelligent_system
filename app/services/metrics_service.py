from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.db.repositories import EventRepository
from app.services.metrics_schemas import HeatmapCell, HeatmapResponse, StoreMetricsResponse
from pipeline.schemas import EventType, PersonType, RetailEvent


PURCHASE_EVENT_TYPES = {EventType.BILLING_QUEUE_JOIN}


@dataclass(slots=True)
class MetricsService:
    repository: EventRepository

    async def get_store_metrics(
        self,
        store_id: UUID,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> StoreMetricsResponse:
        events = await self.repository.list_events_for_store(store_id, start_at, end_at)
        customer_events = [event for event in events if event.person_type == PersonType.CUSTOMER]
        staff_event_count = sum(1 for event in events if event.person_type == PersonType.STAFF)
        unique_visitors = self._unique_customer_count(customer_events)
        purchasing_visitors = self._purchasing_customer_count(customer_events)
        queue_joins = self._events_of_type(customer_events, EventType.BILLING_QUEUE_JOIN)
        queue_abandons = self._events_of_type(customer_events, EventType.BILLING_QUEUE_ABANDON)

        return StoreMetricsResponse(
            store_id=store_id,
            event_count=len(events),
            unique_visitors=unique_visitors,
            staff_event_count=staff_event_count,
            conversion_rate=self._safe_rate(purchasing_visitors, unique_visitors),
            avg_dwell_seconds=self._average_dwell_seconds(customer_events),
            current_queue_depth=self._latest_queue_depth(customer_events),
            max_queue_depth=self._max_queue_depth(customer_events),
            abandonment_rate=self._safe_rate(len(queue_abandons), len(queue_joins)),
            reentry_count=len(self._events_of_type(customer_events, EventType.REENTRY)),
            active_sessions=self._active_session_count(customer_events),
        )

    async def get_heatmap(
        self,
        store_id: UUID,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> HeatmapResponse:
        events = await self.repository.list_events_for_store(store_id, start_at, end_at)
        zone_counts: dict[str, int] = defaultdict(int)
        zone_dwell: dict[str, float] = defaultdict(float)

        for event in events:
            if event.person_type != PersonType.CUSTOMER or not event.zone_id:
                continue
            zone_counts[event.zone_id] += 1
            if event.metadata.dwell_seconds is not None:
                zone_dwell[event.zone_id] += event.metadata.dwell_seconds

        max_signal = max(
            (zone_counts[zone_id] + zone_dwell[zone_id] for zone_id in zone_counts),
            default=0.0,
        )

        cells = [
            HeatmapCell(
                zone_id=zone_id,
                event_count=zone_counts[zone_id],
                dwell_seconds=round(zone_dwell[zone_id], 2),
                normalized_intensity=round(
                    (zone_counts[zone_id] + zone_dwell[zone_id]) / max_signal,
                    4,
                )
                if max_signal > 0
                else 0.0,
            )
            for zone_id in sorted(zone_counts)
        ]
        return HeatmapResponse(store_id=store_id, cells=cells)

    @staticmethod
    def _unique_customer_count(events: list[RetailEvent]) -> int:
        identities = {
            event.global_person_id or str(event.session_id)
            for event in events
            if event.event_type in {EventType.ENTRY, EventType.REENTRY, EventType.ZONE_ENTER}
        }
        return len(identities)

    @staticmethod
    def _purchasing_customer_count(events: list[RetailEvent]) -> int:
        identities = {
            event.global_person_id or str(event.session_id)
            for event in events
            if event.event_type in PURCHASE_EVENT_TYPES
        }
        return len(identities)

    @staticmethod
    def _events_of_type(events: list[RetailEvent], event_type: EventType) -> list[RetailEvent]:
        return [event for event in events if event.event_type == event_type]

    @staticmethod
    def _average_dwell_seconds(events: list[RetailEvent]) -> float:
        dwell_values = [
            event.metadata.dwell_seconds
            for event in events
            if event.event_type == EventType.ZONE_DWELL
            and event.metadata.dwell_seconds is not None
        ]
        if not dwell_values:
            return 0.0
        return round(sum(dwell_values) / len(dwell_values), 2)

    @staticmethod
    def _latest_queue_depth(events: list[RetailEvent]) -> int:
        queue_events = [
            event for event in events if event.metadata.queue_depth is not None
        ]
        if not queue_events:
            return 0
        return queue_events[-1].metadata.queue_depth or 0

    @staticmethod
    def _max_queue_depth(events: list[RetailEvent]) -> int:
        return max(
            (event.metadata.queue_depth or 0 for event in events),
            default=0,
        )

    @staticmethod
    def _active_session_count(events: list[RetailEvent]) -> int:
        open_sessions: set[UUID] = set()
        for event in events:
            if event.event_type in {EventType.ENTRY, EventType.REENTRY, EventType.ZONE_ENTER}:
                open_sessions.add(event.session_id)
            if event.event_type == EventType.EXIT:
                open_sessions.discard(event.session_id)
        return len(open_sessions)

    @staticmethod
    def _safe_rate(numerator: int, denominator: int) -> float:
        if denominator == 0:
            return 0.0
        return round(numerator / denominator, 4)
