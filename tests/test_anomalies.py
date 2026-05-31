# PROMPT:
# Build a production-grade Store Intelligence Platform skeleton before dataset arrival.
#
# CHANGES MADE:
# Added anomaly endpoint tests for queue spikes, conversion drops, dead zones, and
# a normal baseline window with no findings.

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_event_repository
from app.main import create_app
from app.services.anomaly_schemas import AnomalySeverity, AnomalyType
from pipeline.schemas import EventMetadata, EventType, RetailEvent
from tests.fakes import InMemoryEventRepository


STORE_ID = uuid4()
BASE_TIME = datetime(2026, 4, 10, 17, 0, tzinfo=UTC)


def _event(
    event_type: EventType,
    *,
    sequence_number: int,
    store_id: UUID = STORE_ID,
    person_id: str = "customer-1",
    zone_id: str | None = None,
    metadata: EventMetadata | None = None,
    occurred_offset_seconds: int = 0,
) -> RetailEvent:
    return RetailEvent(
        store_id=store_id,
        camera_id="CAM 5" if zone_id == "billing" else "CAM 1",
        event_type=event_type,
        occurred_at=BASE_TIME + timedelta(seconds=occurred_offset_seconds),
        confidence=0.9,
        sequence_number=sequence_number,
        session_id=uuid4(),
        global_person_id=person_id,
        zone_id=zone_id,
        metadata=metadata or EventMetadata(),
    )


async def _client(repository: InMemoryEventRepository) -> AsyncClient:
    app = create_app()

    async def override_repository() -> InMemoryEventRepository:
        return repository

    app.dependency_overrides[get_event_repository] = override_repository
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_anomalies_empty_store_has_no_findings() -> None:
    async with await _client(InMemoryEventRepository()) as client:
        response = await client.get(f"/stores/{STORE_ID}/anomalies")

    body = response.json()
    assert response.status_code == 200
    assert body["anomaly_count"] == 0
    assert body["anomalies"] == []


@pytest.mark.asyncio
async def test_anomalies_detect_queue_spike() -> None:
    repository = InMemoryEventRepository(
        [
            _event(
                EventType.BILLING_QUEUE_JOIN,
                sequence_number=index,
                person_id=f"customer-{index}",
                zone_id="billing",
                metadata=EventMetadata(queue_depth=index),
                occurred_offset_seconds=index,
            )
            for index in range(1, 8)
        ]
    )

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/anomalies")

    anomalies = response.json()["anomalies"]
    queue_spike = next(item for item in anomalies if item["type"] == AnomalyType.QUEUE_SPIKE)
    assert queue_spike["severity"] == AnomalySeverity.CRITICAL
    assert queue_spike["zone_id"] == "billing"
    assert queue_spike["observed_value"] == 7


@pytest.mark.asyncio
async def test_anomalies_detect_conversion_drop() -> None:
    events = [
        _event(
            EventType.ENTRY,
            sequence_number=index,
            person_id=f"visitor-{index}",
            occurred_offset_seconds=index,
        )
        for index in range(1, 5)
    ]
    repository = InMemoryEventRepository(events)

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/anomalies")

    anomalies = response.json()["anomalies"]
    conversion_drop = next(
        item for item in anomalies if item["type"] == AnomalyType.CONVERSION_DROP
    )
    assert conversion_drop["severity"] == AnomalySeverity.CRITICAL
    assert conversion_drop["observed_value"] == 0


@pytest.mark.asyncio
async def test_anomalies_detect_dead_zone() -> None:
    events = [
        _event(
            EventType.ZONE_ENTER,
            sequence_number=index,
            person_id=f"visitor-{index}",
            zone_id="sales-floor",
            occurred_offset_seconds=index,
        )
        for index in range(1, 7)
    ]
    repository = InMemoryEventRepository(events)

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/anomalies")

    dead_zones = [
        item for item in response.json()["anomalies"] if item["type"] == AnomalyType.DEAD_ZONE
    ]
    assert {item["zone_id"] for item in dead_zones} >= {"billing", "makeup-unit", "promo-endcap"}
    assert all(item["severity"] == AnomalySeverity.INFO for item in dead_zones)


@pytest.mark.asyncio
async def test_anomalies_normal_window_has_no_findings() -> None:
    events = [
        _event(EventType.ENTRY, sequence_number=1, person_id="buyer-1"),
        _event(
            EventType.ZONE_ENTER,
            sequence_number=2,
            person_id="buyer-1",
            zone_id="sales-floor",
        ),
        _event(
            EventType.ZONE_DWELL,
            sequence_number=3,
            person_id="buyer-1",
            zone_id="makeup-unit",
            metadata=EventMetadata(dwell_seconds=18),
        ),
        _event(
            EventType.BILLING_QUEUE_JOIN,
            sequence_number=4,
            person_id="buyer-1",
            zone_id="billing",
            metadata=EventMetadata(queue_depth=1),
        ),
        _event(
            EventType.ZONE_ENTER,
            sequence_number=5,
            person_id="buyer-2",
            zone_id="promo-endcap",
        ),
    ]
    repository = InMemoryEventRepository(events)

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/anomalies")

    assert response.status_code == 200
    assert response.json()["anomaly_count"] == 0
