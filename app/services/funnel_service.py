from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.db.repositories import EventRepository
from app.services.funnel_schemas import FunnelResponse, FunnelStage, FunnelStageMetric
from pipeline.schemas import EventType, PersonType, RetailEvent


@dataclass(slots=True)
class SessionProgress:
    session_id: UUID
    identity: str
    person_type: PersonType
    stages: set[FunnelStage] = field(default_factory=set)
    had_reentry: bool = False


@dataclass(slots=True)
class FunnelService:
    repository: EventRepository

    async def get_store_funnel(
        self,
        store_id: UUID,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> FunnelResponse:
        events = await self.repository.list_events_for_store(store_id, start_at, end_at)
        progress_by_identity = self._build_session_progress(events)
        customer_progress = [
            progress
            for progress in progress_by_identity.values()
            if progress.person_type == PersonType.CUSTOMER
        ]
        staff_sessions_excluded = sum(
            1
            for progress in progress_by_identity.values()
            if progress.person_type == PersonType.STAFF
        )

        stage_counts = {
            stage: sum(1 for progress in customer_progress if stage in progress.stages)
            for stage in FunnelStage
        }
        stages = self._stage_metrics(stage_counts)
        entry_sessions = stage_counts[FunnelStage.ENTRY]
        completed_sessions = stage_counts[FunnelStage.PURCHASE_PROXY]

        return FunnelResponse(
            store_id=store_id,
            stages=stages,
            entry_sessions=entry_sessions,
            completed_sessions=completed_sessions,
            reentry_sessions=sum(1 for progress in customer_progress if progress.had_reentry),
            staff_sessions_excluded=staff_sessions_excluded,
            overall_conversion_rate=self._safe_rate(completed_sessions, entry_sessions),
            notes=self._notes(events, completed_sessions),
        )

    def _build_session_progress(
        self,
        events: list[RetailEvent],
    ) -> dict[str, SessionProgress]:
        progress_by_identity: dict[str, SessionProgress] = {}

        for event in events:
            identity = event.global_person_id or str(event.session_id)
            progress = progress_by_identity.setdefault(
                identity,
                SessionProgress(
                    session_id=event.session_id,
                    identity=identity,
                    person_type=event.person_type,
                ),
            )
            if event.person_type == PersonType.STAFF:
                progress.person_type = PersonType.STAFF

            stage = self._stage_for_event(event)
            if stage is not None:
                progress.stages.add(stage)
            if event.event_type == EventType.REENTRY:
                progress.had_reentry = True
                progress.stages.add(FunnelStage.ENTRY)

        self._apply_stage_closure(progress_by_identity)
        return progress_by_identity

    @staticmethod
    def _stage_for_event(event: RetailEvent) -> FunnelStage | None:
        if event.event_type in {EventType.ENTRY, EventType.REENTRY}:
            return FunnelStage.ENTRY
        if event.event_type in {EventType.ZONE_ENTER, EventType.ZONE_EXIT}:
            if event.zone_id and event.zone_id.lower() in {"billing", "cash-counter"}:
                return FunnelStage.BILLING_INTENT
            return FunnelStage.BROWSE
        if event.event_type == EventType.ZONE_DWELL:
            return FunnelStage.DWELL
        if event.event_type == EventType.BILLING_QUEUE_JOIN:
            return FunnelStage.PURCHASE_PROXY
        return None

    @staticmethod
    def _apply_stage_closure(progress_by_identity: dict[str, SessionProgress]) -> None:
        for progress in progress_by_identity.values():
            if FunnelStage.PURCHASE_PROXY in progress.stages:
                progress.stages.add(FunnelStage.BILLING_INTENT)
            if FunnelStage.BILLING_INTENT in progress.stages:
                progress.stages.add(FunnelStage.DWELL)
            if FunnelStage.DWELL in progress.stages:
                progress.stages.add(FunnelStage.BROWSE)
            if FunnelStage.BROWSE in progress.stages:
                progress.stages.add(FunnelStage.ENTRY)

    def _stage_metrics(
        self,
        stage_counts: dict[FunnelStage, int],
    ) -> list[FunnelStageMetric]:
        ordered_stages = list(FunnelStage)
        entry_count = stage_counts[FunnelStage.ENTRY]
        metrics: list[FunnelStageMetric] = []
        previous_count = 0

        for index, stage in enumerate(ordered_stages):
            count = stage_counts[stage]
            if index == 0:
                conversion_from_previous = 1.0 if count > 0 else 0.0
                dropoff = 0
            else:
                conversion_from_previous = self._safe_rate(count, previous_count)
                dropoff = max(previous_count - count, 0)
            metrics.append(
                FunnelStageMetric(
                    stage=stage,
                    count=count,
                    conversion_from_previous=conversion_from_previous,
                    conversion_from_entry=self._safe_rate(count, entry_count),
                    dropoff_from_previous=dropoff,
                )
            )
            previous_count = count
        return metrics

    @staticmethod
    def _notes(events: list[RetailEvent], completed_sessions: int) -> list[str]:
        notes = [
            "Purchase proxy is currently mapped to billing queue intent until POS/session linking is implemented."
        ]
        if events and completed_sessions == 0:
            notes.append("No purchase-proxy events observed in this event window.")
        return notes

    @staticmethod
    def _safe_rate(numerator: int, denominator: int) -> float:
        if denominator == 0:
            return 0.0
        return round(numerator / denominator, 4)
