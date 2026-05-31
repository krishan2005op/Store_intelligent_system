# PROMPT:
# Build a production-grade Store Intelligence Platform skeleton before dataset arrival.
#
# CHANGES MADE:
# Added funnel endpoint tests for empty stores, session progression, staff exclusion,
# reentry deduplication, and billing-queue purchase proxy behavior.

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_event_repository
from app.main import create_app
from app.services.funnel_schemas import FunnelStage
from pipeline.schemas import EventMetadata, EventType, PersonType, RetailEvent
from tests.fakes import InMemoryEventRepository


STORE_ID = uuid4()
BASE_TIME = datetime(2026, 4, 10, 16, 30, tzinfo=UTC)


def _event(
    event_type: EventType,
    *,
    sequence_number: int,
    store_id: UUID = STORE_ID,
    person_id: str = "customer-1",
    session_id: UUID | None = None,
    person_type: PersonType = PersonType.CUSTOMER,
    zone_id: str | None = None,
    metadata: EventMetadata | None = None,
    occurred_offset_seconds: int = 0,
) -> RetailEvent:
    return RetailEvent(
        store_id=store_id,
        camera_id="CAM 3" if event_type in {EventType.ENTRY, EventType.REENTRY} else "CAM 1",
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
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


def _stage_counts(body: dict[str, object]) -> dict[str, int]:
    stages = body["stages"]
    assert isinstance(stages, list)
    return {str(stage["stage"]): int(stage["count"]) for stage in stages}


@pytest.mark.asyncio
async def test_funnel_empty_store_returns_zeroes() -> None:
    async with await _client(InMemoryEventRepository()) as client:
        response = await client.get(f"/stores/{STORE_ID}/funnel")

    body = response.json()
    counts = _stage_counts(body)
    assert response.status_code == 200
    assert body["entry_sessions"] == 0
    assert body["completed_sessions"] == 0
    assert body["overall_conversion_rate"] == 0
    assert all(count == 0 for count in counts.values())


@pytest.mark.asyncio
async def test_funnel_tracks_stage_dropoff() -> None:
    buyer_session = uuid4()
    browser_session = uuid4()
    repository = InMemoryEventRepository(
        [
            _event(EventType.ENTRY, sequence_number=1, person_id="buyer", session_id=buyer_session),
            _event(
                EventType.ZONE_ENTER,
                sequence_number=2,
                person_id="buyer",
                session_id=buyer_session,
                zone_id="sales-floor",
            ),
            _event(
                EventType.ZONE_DWELL,
                sequence_number=3,
                person_id="buyer",
                session_id=buyer_session,
                zone_id="makeup-unit",
                metadata=EventMetadata(dwell_seconds=22),
            ),
            _event(
                EventType.BILLING_QUEUE_JOIN,
                sequence_number=4,
                person_id="buyer",
                session_id=buyer_session,
                zone_id="billing",
                metadata=EventMetadata(queue_depth=1),
            ),
            _event(EventType.ENTRY, sequence_number=5, person_id="browser", session_id=browser_session),
            _event(
                EventType.ZONE_ENTER,
                sequence_number=6,
                person_id="browser",
                session_id=browser_session,
                zone_id="sales-floor",
            ),
        ]
    )

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/funnel")

    body = response.json()
    counts = _stage_counts(body)
    assert counts[FunnelStage.ENTRY] == 2
    assert counts[FunnelStage.BROWSE] == 2
    assert counts[FunnelStage.DWELL] == 1
    assert counts[FunnelStage.BILLING_INTENT] == 1
    assert counts[FunnelStage.PURCHASE_PROXY] == 1
    assert body["overall_conversion_rate"] == 0.5


@pytest.mark.asyncio
async def test_funnel_excludes_staff_sessions() -> None:
    staff_session = uuid4()
    customer_session = uuid4()
    repository = InMemoryEventRepository(
        [
            _event(
                EventType.ZONE_ENTER,
                sequence_number=1,
                person_id="staff-1",
                session_id=staff_session,
                person_type=PersonType.STAFF,
                zone_id="back-area",
            ),
            _event(
                EventType.ENTRY,
                sequence_number=2,
                person_id="customer-1",
                session_id=customer_session,
            ),
        ]
    )

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/funnel")

    body = response.json()
    assert body["staff_sessions_excluded"] == 1
    assert body["entry_sessions"] == 1


@pytest.mark.asyncio
async def test_funnel_reentry_dedupes_identity() -> None:
    session_id = uuid4()
    repository = InMemoryEventRepository(
        [
            _event(EventType.ENTRY, sequence_number=1, person_id="returning", session_id=session_id),
            _event(EventType.EXIT, sequence_number=2, person_id="returning", session_id=session_id),
            _event(EventType.REENTRY, sequence_number=3, person_id="returning", session_id=session_id),
        ]
    )

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/funnel")

    body = response.json()
    counts = _stage_counts(body)
    assert counts[FunnelStage.ENTRY] == 1
    assert body["reentry_sessions"] == 1


@pytest.mark.asyncio
async def test_funnel_time_window_filters_events() -> None:
    session_id = uuid4()
    repository = InMemoryEventRepository(
        [
            _event(
                EventType.ENTRY,
                sequence_number=1,
                person_id="customer-1",
                session_id=session_id,
                occurred_offset_seconds=0,
            ),
            _event(
                EventType.BILLING_QUEUE_JOIN,
                sequence_number=2,
                person_id="customer-1",
                session_id=session_id,
                zone_id="billing",
                metadata=EventMetadata(queue_depth=1),
                occurred_offset_seconds=120,
            ),
        ]
    )
    end_at = (BASE_TIME + timedelta(seconds=30)).isoformat()

    async with await _client(repository) as client:
        response = await client.get(f"/stores/{STORE_ID}/funnel", params={"end_at": end_at})

    body = response.json()
    counts = _stage_counts(body)
    assert counts[FunnelStage.ENTRY] == 1
    assert counts[FunnelStage.PURCHASE_PROXY] == 0
