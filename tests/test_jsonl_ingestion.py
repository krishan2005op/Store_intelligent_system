from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from pipeline.run import _run_ingest
from pipeline.schemas import EventType, RetailEvent


@pytest.mark.asyncio
async def test_run_ingest_via_api() -> None:
    # Create test events
    events = [
        RetailEvent(
            store_id=uuid4(),
            camera_id="cam-1",
            event_type=EventType.ENTRY,
            occurred_at=datetime.now(UTC),
            confidence=0.9,
            sequence_number=1,
        )
    ]

    args = argparse.Namespace(file="mock_events.jsonl", api_url="http://testserver")

    with patch("pipeline.dataset_runner.load_events_from_jsonl", return_value=events) as mock_load:
        # Mock httpx AsyncClient post
        mock_post = AsyncMock()
        mock_post.return_value.status_code = 202

        # We patch the AsyncClient's enter return object
        mock_client = MagicMock()
        mock_client.__aenter__.return_value.post = mock_post

        with patch("httpx.AsyncClient", return_value=mock_client):
            await _run_ingest(args)

            mock_load.assert_called_once_with(Path("mock_events.jsonl"))
            mock_post.assert_called_once()

            # Verify arguments
            url = mock_post.call_args[0][0]
            json_payload = mock_post.call_args[1]["json"]
            assert url == "http://testserver/events/ingest"
            assert len(json_payload["events"]) == 1
            assert json_payload["events"][0]["camera_id"] == "cam-1"


@pytest.mark.asyncio
async def test_run_ingest_via_db() -> None:
    events = [
        RetailEvent(
            store_id=uuid4(),
            camera_id="cam-2",
            event_type=EventType.ENTRY,
            occurred_at=datetime.now(UTC),
            confidence=0.85,
            sequence_number=2,
        )
    ]

    args = argparse.Namespace(file="mock_events.jsonl", api_url=None)

    # Mock session contexts
    mock_session = MagicMock()
    mock_session_context = MagicMock()
    mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_context.__aexit__ = AsyncMock(return_value=None)

    mock_service_instance = AsyncMock()
    mock_service_instance.ingest_events.return_value = MagicMock(
        accepted_count=1,
        duplicate_count=0,
        rejected_count=0,
    )

    with patch("pipeline.dataset_runner.load_events_from_jsonl", return_value=events) as mock_load:
        # Mock AsyncSessionFactory to yield our mock session context
        with patch("app.db.session.AsyncSessionFactory", return_value=mock_session_context):
            with patch("app.services.ingestion_service.IngestionService", return_value=mock_service_instance) as mock_service_cls:
                await _run_ingest(args)

                mock_load.assert_called_once_with(Path("mock_events.jsonl"))
                mock_service_cls.assert_called_once()
                mock_service_instance.ingest_events.assert_called_once_with(events)
