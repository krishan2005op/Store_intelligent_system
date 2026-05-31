# PROMPT:
# Build a production-grade Store Intelligence Platform skeleton before dataset arrival.
#
# CHANGES MADE:
# Added health endpoint tests for empty feeds, stale simulated event feeds, and
# graceful degraded responses when storage is unavailable.

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_event_repository
from app.main import create_app
from pipeline.schemas import EventType, RetailEvent
from tests.fakes import InMemoryEventRepository


class UnavailableEventRepository(InMemoryEventRepository):
    async def latest_event_at(self, store_id: object | None = None) -> datetime | None:
        raise OSError("database unavailable")


def _event_at(occurred_at: datetime) -> RetailEvent:
    return RetailEvent(
        store_id=uuid4(),
        camera_id="entrance-cam-01",
        event_type=EventType.ENTRY,
        occurred_at=occurred_at,
        confidence=0.91,
        sequence_number=1,
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
async def test_health_is_ok_with_empty_feed() -> None:
    async with await _client(InMemoryEventRepository()) as client:
        response = await client.get("/health")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["latest_event_at"] is None
    assert body["feed_stale"] is False
    assert body["database_connected"] is True


@pytest.mark.asyncio
async def test_health_marks_stale_feed() -> None:
    stale_event = _event_at(datetime.now(UTC) - timedelta(minutes=10))
    repository = InMemoryEventRepository(initial_events=[stale_event])

    async with await _client(repository) as client:
        response = await client.get("/health")

    body = response.json()
    assert response.status_code == 200
    assert body["latest_event_at"] is not None
    assert body["feed_stale"] is True
    assert body["database_connected"] is True


@pytest.mark.asyncio
async def test_health_degrades_when_database_is_unavailable() -> None:
    async with await _client(UnavailableEventRepository()) as client:
        response = await client.get("/health")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "degraded"
    assert body["database_connected"] is False
    assert body["latest_event_at"] is None
