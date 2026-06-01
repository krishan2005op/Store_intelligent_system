from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.websocket_service import manager
from pipeline.schemas import EventType, RetailEvent


def test_dashboard_http_routes() -> None:
    app = create_app()
    client = TestClient(app)

    # Test HTTP GET endpoints return the template
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Store Intelligence Platform" in response.text

    response = client.get("/")
    assert response.status_code == 200
    assert "Store Intelligence Platform" in response.text


def test_dashboard_websocket_broadcast() -> None:
    app = create_app()
    client = TestClient(app)
    store_id = uuid4()

    with client.websocket_connect(f"/stores/{store_id}/live") as websocket:
        # Mock event
        event = RetailEvent(
            store_id=store_id,
            camera_id="entrance-cam-01",
            event_type=EventType.ENTRY,
            occurred_at=datetime.now(UTC),
            confidence=0.95,
            sequence_number=1,
        )

        import asyncio

        # Broadcast event to subscribers
        asyncio.run(manager.broadcast_events(store_id, [event]))

        # Retrieve broadcasted json
        data = websocket.receive_json()
        assert data["store_id"] == str(store_id)
        assert len(data["events"]) == 1
        assert data["events"][0]["event_type"] == "ENTRY"
        assert data["events"][0]["camera_id"] == "entrance-cam-01"
