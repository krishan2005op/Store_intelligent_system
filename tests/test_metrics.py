# PROMPT:
# Build a production-grade Store Intelligence Platform skeleton before dataset arrival.
#
# CHANGES MADE:
# Added metrics and heatmap tests for empty stores, staff-only traffic, zero-purchase
# sessions, reentry deduplication, queue abandonment, and normalized zone intensity.

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_event_repository
from app.main import create_app
from pipeline.schemas import EventMetadata, EventType, PersonType, RetailEvent
from tests.fakes import InMemoryEventRepository


STORE_ID = uuid4()
BASE_TIME = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def _event(
    event_type: EventType,
    *,
    store_id: UUID = STORE_ID,
    sequence_number: int = 1,
    person_id: str = "customer-1",
    session_id: UUID | None = None,
    person_type: PersonType = PersonType.CUSTOMER,
    zone_id: str | None = None,
    metadata: EventMetadata | None = None,
    occurred_offset_seconds: int = 0,
) -> RetailEvent:
    return RetailEvent(
        store_id=store_id,
        camera_id="test-cam-01",
        event_type=event_type,
        occurred_at=BASE_TIME + timedelta(seconds=occurred_offset_seconds),
        confidence=0.9,
        sequence_number=sequence_number,
        session_id=session_id or uuid4(),
        global_person_id=person_id,
        person_type=person_type,
        zone_id=zone_id,
        metadata=metadata or EventMetadata(),
    )


async def _client(repository: InMemoryEventRepository) -> AsyncClient:
    app = create_app()

    async def override_repository() -> InMemoryEventRepository:
        return repository

    app.dependency_overrides[get_event_repository] = override_repository
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


@pytest.mark.asyncio
async def test_metrics_empty_store_returns_zeroes() -> None:
    async with await _client(InMemoryEventRepository()) as client:
        response = await client.get(f"/stores/{STORE_ID}/metrics")

    body = response.json()
    assert response.status_code == 200
    assert body["event_count"] == 0
    assert body["unique_visitors"] == 0
    assert body["conversion_rate"] == 0
    assert body["avg_dwell_seconds"] == 0
    assert body["current_queue_depth"] == 0


@pytest.mark.asyncio
async def test_metrics_all_staff_does_not_count_as_visitors() -> None:
    staff_session = uuid4()
    repository = InMemoryEventRepository(
        [
            _event(
                EventType.ZONE_ENTER,
                sequence_number=1,
                person_id="staff-1",
                session_id=staff_session,
                person_type=PersonType.STAFF,
                zone_id="sales-floor",
            ),
            _event(
                EventType.ZONE_EXIT,
                sequence_number=2,
                person_id="staff-1",
                session_id=staff_session,
                person_type=PersonType.STAFF,
                zone_id="sales-floor",
            ),
        ]
    )

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/metrics")

    body = response.json()
    assert body["event_count"] == 2
    assert body["staff_event_count"] == 2
    assert body["unique_visitors"] == 0
    assert body["conversion_rate"] == 0


@pytest.mark.asyncio
async def test_metrics_zero_purchase_has_zero_conversion() -> None:
    session_id = uuid4()
    repository = InMemoryEventRepository(
        [
            _event(EventType.ENTRY, sequence_number=1, person_id="customer-1", session_id=session_id),
            _event(
                EventType.ZONE_DWELL,
                sequence_number=2,
                person_id="customer-1",
                session_id=session_id,
                zone_id="aisle-1",
                metadata=EventMetadata(dwell_seconds=30),
            ),
        ]
    )

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/metrics")

    body = response.json()
    assert body["unique_visitors"] == 1
    assert body["conversion_rate"] == 0
    assert body["avg_dwell_seconds"] == 30


@pytest.mark.asyncio
async def test_metrics_reentry_dedupes_unique_visitor_identity() -> None:
    session_id = uuid4()
    repository = InMemoryEventRepository(
        [
            _event(EventType.ENTRY, sequence_number=1, person_id="returning-1", session_id=session_id),
            _event(EventType.EXIT, sequence_number=2, person_id="returning-1", session_id=session_id),
            _event(
                EventType.REENTRY,
                sequence_number=3,
                person_id="returning-1",
                session_id=session_id,
            ),
        ]
    )

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/metrics")

    body = response.json()
    assert body["unique_visitors"] == 1
    assert body["reentry_count"] == 1
    assert body["active_sessions"] == 1


@pytest.mark.asyncio
async def test_metrics_queue_abandonment_rate() -> None:
    repository = InMemoryEventRepository(
        [
            _event(
                EventType.BILLING_QUEUE_JOIN,
                sequence_number=1,
                person_id="customer-1",
                zone_id="billing",
                metadata=EventMetadata(queue_depth=1),
            ),
            _event(
                EventType.BILLING_QUEUE_JOIN,
                sequence_number=2,
                person_id="customer-2",
                zone_id="billing",
                metadata=EventMetadata(queue_depth=2),
            ),
            _event(
                EventType.BILLING_QUEUE_ABANDON,
                sequence_number=3,
                person_id="customer-2",
                zone_id="billing",
                metadata=EventMetadata(queue_depth=1),
            ),
        ]
    )

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/metrics")

    body = response.json()
    assert body["max_queue_depth"] == 2
    assert body["current_queue_depth"] == 1
    assert body["abandonment_rate"] == 0.5


@pytest.mark.asyncio
async def test_heatmap_normalizes_zone_intensity() -> None:
    repository = InMemoryEventRepository(
        [
            _event(
                EventType.ZONE_DWELL,
                sequence_number=1,
                person_id="customer-1",
                zone_id="aisle-1",
                metadata=EventMetadata(dwell_seconds=20),
            ),
            _event(
                EventType.ZONE_DWELL,
                sequence_number=2,
                person_id="customer-2",
                zone_id="aisle-2",
                metadata=EventMetadata(dwell_seconds=5),
            ),
        ]
    )

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/heatmap")

    body = response.json()
    cells = {cell["zone_id"]: cell for cell in body["cells"]}
    assert response.status_code == 200
    assert cells["aisle-1"]["normalized_intensity"] == 1.0
    assert 0 < cells["aisle-2"]["normalized_intensity"] < 1
