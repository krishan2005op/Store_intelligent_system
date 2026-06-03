from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.dataset_config import STORE_2_PROFILE
from pipeline.dataset_runner import load_events_from_jsonl
from pipeline.run import _run_ingest
from pipeline.schemas import EventSource, EventType, RetailEvent


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


def test_load_external_sample_jsonl_adapts_store_2_events(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "sample_events.jsonl"
    jsonl_path.write_text(
        "\n".join(
            [
                (
                    '{"event_type":"entry","id_token":"ID_60001","store_code":"store_1076",'
                    '"camera_id":"cam1","event_timestamp":"2026-03-08T18:10:05.120000",'
                    '"is_staff":false,"gender":"female","age":27,"group_id":"G1","group_size":2}'
                ),
                (
                    '{"event_type":"zone_entered","track_id":101,"store_id":"ST1076",'
                    '"camera_id":"CAM2","zone_id":"PURPLLE_MUM_1076_Z01","zone_name":"Left Shelf",'
                    '"zone_type":"SHELF","event_time":"2026-03-08T18:10:35.120000"}'
                ),
                (
                    '{"event_type":"queue_abandoned","queue_event_id":"Q1","track_id":101,'
                    '"store_id":"ST1076","camera_id":"PURPLLE_MUM_1076_CAM6",'
                    '"zone_id":"PURPLLE_MUM_1076_Z_BILLING_01",'
                    '"queue_join_ts":"2026-03-08T18:12:35.120000","queue_exit_ts":"2026-03-08T18:15:35.120000",'
                    '"wait_seconds":180,"queue_position_at_join":3,"abandoned":true}'
                ),
            ]
        ),
        encoding="utf-8",
    )

    events = load_events_from_jsonl(jsonl_path)

    assert [event.event_type for event in events] == [
        EventType.ENTRY,
        EventType.ZONE_ENTER,
        EventType.BILLING_QUEUE_ABANDON,
    ]
    assert str(events[0].store_id) == STORE_2_PROFILE.canonical_store_uuid
    assert events[0].source == EventSource.BATCH_REPLAY
    assert events[0].occurred_at.tzinfo is not None
    assert events[2].metadata.queue_depth == 3
    assert events[2].metadata.wait_seconds == 180


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
