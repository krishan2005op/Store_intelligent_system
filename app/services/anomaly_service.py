from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.db.repositories import EventRepository
from app.services.anomaly_schemas import (
    AnomalyFinding,
    AnomalyResponse,
    AnomalySeverity,
    AnomalyType,
)
from app.services.metrics_service import MetricsService
from pipeline.schemas import EventType, PersonType, RetailEvent


EXPECTED_CUSTOMER_ZONES = frozenset(
    {
        "sales-floor",
        "makeup-unit",
        "billing",
        "promo-endcap",
    }
)


@dataclass(frozen=True, slots=True)
class AnomalyThresholds:
    queue_warn_depth: int = 4
    queue_critical_depth: int = 7
    min_visitors_for_conversion_check: int = 3
    conversion_warn_rate: float = 0.2
    conversion_critical_rate: float = 0.08
    min_events_for_dead_zone_check: int = 5


@dataclass(slots=True)
class AnomalyService:
    repository: EventRepository
    thresholds: AnomalyThresholds = AnomalyThresholds()

    async def get_store_anomalies(
        self,
        store_id: UUID,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> AnomalyResponse:
        events = await self.repository.list_events_for_store(store_id, start_at, end_at)
        metrics = await MetricsService(self.repository).get_store_metrics(
            store_id,
            start_at,
            end_at,
        )
        findings: list[AnomalyFinding] = []
        findings.extend(self._queue_spike_findings(store_id, metrics.max_queue_depth))
        findings.extend(
            self._conversion_drop_findings(
                store_id,
                unique_visitors=metrics.unique_visitors,
                conversion_rate=metrics.conversion_rate,
            )
        )
        findings.extend(self._dead_zone_findings(store_id, events))

        return AnomalyResponse(
            store_id=store_id,
            generated_at=datetime.now(UTC),
            anomaly_count=len(findings),
            anomalies=findings,
        )

    def _queue_spike_findings(
        self,
        store_id: UUID,
        max_queue_depth: int,
    ) -> list[AnomalyFinding]:
        if max_queue_depth < self.thresholds.queue_warn_depth:
            return []

        severity = (
            AnomalySeverity.CRITICAL
            if max_queue_depth >= self.thresholds.queue_critical_depth
            else AnomalySeverity.WARN
        )
        return [
            AnomalyFinding(
                anomaly_id=f"{store_id}:queue-spike",
                type=AnomalyType.QUEUE_SPIKE,
                severity=severity,
                title="Billing queue depth exceeded baseline",
                description=(
                    f"Maximum observed queue depth was {max_queue_depth}, above "
                    f"the warning threshold of {self.thresholds.queue_warn_depth}."
                ),
                suggested_action=(
                    "Open an additional billing counter or move a staff member to checkout."
                ),
                observed_value=float(max_queue_depth),
                threshold_value=float(self.thresholds.queue_warn_depth),
                zone_id="billing",
                metadata={"critical_threshold": self.thresholds.queue_critical_depth},
            )
        ]

    def _conversion_drop_findings(
        self,
        store_id: UUID,
        *,
        unique_visitors: int,
        conversion_rate: float,
    ) -> list[AnomalyFinding]:
        if unique_visitors < self.thresholds.min_visitors_for_conversion_check:
            return []
        if conversion_rate >= self.thresholds.conversion_warn_rate:
            return []

        severity = (
            AnomalySeverity.CRITICAL
            if conversion_rate <= self.thresholds.conversion_critical_rate
            else AnomalySeverity.WARN
        )
        return [
            AnomalyFinding(
                anomaly_id=f"{store_id}:conversion-drop",
                type=AnomalyType.CONVERSION_DROP,
                severity=severity,
                title="Conversion rate below baseline",
                description=(
                    f"Observed conversion rate was {conversion_rate:.2%} across "
                    f"{unique_visitors} visitors."
                ),
                suggested_action=(
                    "Review staff coverage, checkout friction, and product availability "
                    "for this time window."
                ),
                observed_value=conversion_rate,
                threshold_value=self.thresholds.conversion_warn_rate,
                metadata={
                    "unique_visitors": unique_visitors,
                    "critical_threshold": self.thresholds.conversion_critical_rate,
                },
            )
        ]

    def _dead_zone_findings(
        self,
        store_id: UUID,
        events: list[RetailEvent],
    ) -> list[AnomalyFinding]:
        customer_events = [
            event for event in events if event.person_type == PersonType.CUSTOMER
        ]
        if len(customer_events) < self.thresholds.min_events_for_dead_zone_check:
            return []

        observed_zones = {
            event.zone_id
            for event in customer_events
            if event.zone_id
            and event.event_type
            in {
                EventType.ZONE_ENTER,
                EventType.ZONE_EXIT,
                EventType.ZONE_DWELL,
                EventType.BILLING_QUEUE_JOIN,
                EventType.BILLING_QUEUE_ABANDON,
            }
        }
        missing_zones = sorted(EXPECTED_CUSTOMER_ZONES - observed_zones)

        return [
            AnomalyFinding(
                anomaly_id=f"{store_id}:dead-zone:{zone_id}",
                type=AnomalyType.DEAD_ZONE,
                severity=AnomalySeverity.INFO,
                title="Expected customer zone has no observed activity",
                description=f"No customer zone activity was observed for {zone_id}.",
                suggested_action=(
                    "Verify camera coverage and review merchandising or signage for this zone."
                ),
                observed_value=0.0,
                threshold_value=1.0,
                zone_id=zone_id,
                metadata={"expected_zones": sorted(EXPECTED_CUSTOMER_ZONES)},
            )
            for zone_id in missing_zones
        ]
