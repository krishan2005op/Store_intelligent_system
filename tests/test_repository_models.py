# PROMPT:
# Build a production-grade Store Intelligence Platform skeleton before dataset arrival.
#
# CHANGES MADE:
# Added model conversion test to ensure SQLAlchemy event records round-trip the
# shared RetailEvent schema used by pipeline, API, and metrics services.

from datetime import UTC, datetime
from uuid import uuid4

from app.db.models import RetailEventRecord
from pipeline.schemas import BoundingBox, EventMetadata, EventType, RetailEvent


def test_retail_event_record_round_trips_schema() -> None:
    event = RetailEvent(
        store_id=uuid4(),
        camera_id="entrance-cam-01",
        event_type=EventType.ZONE_DWELL,
        occurred_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        confidence=0.88,
        sequence_number=7,
        session_id=uuid4(),
        track_id="track-7",
        global_person_id="person-7",
        zone_id="promo-endcap",
        bbox=BoundingBox(x=10, y=20, width=30, height=40),
        metadata=EventMetadata(dwell_seconds=14.5, scenario="round_trip"),
    )

    record = RetailEventRecord.from_schema(event)
    restored = record.to_schema()

    assert restored.event_id == event.event_id
    assert restored.event_type == EventType.ZONE_DWELL
    assert restored.bbox == event.bbox
    assert restored.metadata.dwell_seconds == 14.5
