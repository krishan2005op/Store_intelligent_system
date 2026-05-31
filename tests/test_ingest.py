# PROMPT:
# Build a production-grade Store Intelligence Platform skeleton before dataset arrival.
#
# CHANGES MADE:
# Added API ingestion tests for accepted events, idempotent duplicate handling,
# structured validation errors, and request trace propagation.

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_event_repository
from app.main import create_app
from pipeline.schemas import EventMetadata, EventType, RetailEvent
from tests.fakes import InMemoryEventRepository


def _event(**overrides: object) -> RetailEvent:
    payload: dict[str, object] = {
        "store_id": uuid4(),
        "camera_id": "entrance-cam-01",
        "event_type": EventType.ENTRY,
        "occurred_at": datetime.now(UTC),
        "confidence": 0.92,
        "sequence_number": 1,
    }
    payload.update(overrides)
    return RetailEvent.model_validate(payload)


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
async def test_ingest_accepts_valid_event_batch() -> None:
    repository = InMemoryEventRepository()
    event = _event()

    async with await _client(repository) as client:
        response = await client.post(
            "/events/ingest",
            json={"events": [event.model_dump(mode="json")]},
        )

    body = response.json()
    assert response.status_code == 202
    assert body["accepted_count"] == 1
    assert body["duplicate_count"] == 0
    assert body["results"][0]["accepted"] is True
    assert event.event_id in repository.events


@pytest.mark.asyncio
async def test_ingest_marks_existing_event_as_duplicate() -> None:
    event = _event()
    repository = InMemoryEventRepository(initial_events=[event])

    async with await _client(repository) as client:
        response = await client.post(
            "/events/ingest",
            json={"events": [event.model_dump(mode="json")]},
        )

    body = response.json()
    assert response.status_code == 202
    assert body["accepted_count"] == 0
    assert body["duplicate_count"] == 1
    assert body["results"][0]["duplicate"] is True


@pytest.mark.asyncio
async def test_ingest_marks_duplicate_event_inside_same_batch() -> None:
    event = _event()
    repository = InMemoryEventRepository()

    async with await _client(repository) as client:
        response = await client.post(
            "/events/ingest",
            json={"events": [event.model_dump(mode="json"), event.model_dump(mode="json")]},
        )

    body = response.json()
    assert response.status_code == 202
    assert body["accepted_count"] == 1
    assert body["duplicate_count"] == 1
    assert body["results"][1]["message"] == "Duplicate event_id in request batch"


@pytest.mark.asyncio
async def test_ingest_returns_structured_validation_error() -> None:
    repository = InMemoryEventRepository()

    async with await _client(repository) as client:
        response = await client.post("/events/ingest", json={"events": []})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "REQUEST_VALIDATION_ERROR"
    assert UUID(body["trace_id"])
    assert body["details"]["errors"]


@pytest.mark.asyncio
async def test_ingest_propagates_trace_header() -> None:
    repository = InMemoryEventRepository()
    event = _event(
        event_type=EventType.BILLING_QUEUE_JOIN,
        zone_id="billing",
        metadata=EventMetadata(queue_depth=3),
    )
    trace_id = uuid4()

    async with await _client(repository) as client:
        response = await client.post(
            "/events/ingest",
            json={"events": [event.model_dump(mode="json")]},
            headers={"X-Trace-Id": str(trace_id)},
        )

    assert response.status_code == 202
    assert response.headers["X-Trace-Id"] == str(trace_id)
    assert response.json()["trace_id"] == str(trace_id)
