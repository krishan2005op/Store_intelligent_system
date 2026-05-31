# PROMPT:
# Build a production-grade Store Intelligence Platform skeleton before dataset arrival.
#
# CHANGES MADE:
# Added schema-level tests for validation rules, UUID defaults, timezone handling,
# queue/dwell event semantics, and pre-dataset simulator/adapters.

from datetime import UTC, datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from pipeline.detect import MockDetector, VideoFrame
from pipeline.reid import MockReID
from pipeline.schemas import EventMetadata, EventType, RetailEvent
from pipeline.simulator import RetailEventSimulator, SimulationProfile
from pipeline.tracker import MockTracker
from pipeline.zones import MockZoneResolver


def _base_event(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "store_id": uuid4(),
        "camera_id": "entrance-cam-01",
        "event_type": EventType.ENTRY,
        "occurred_at": datetime.now(UTC),
        "confidence": 0.91,
        "sequence_number": 1,
    }
    payload.update(overrides)
    return payload


def test_event_defaults_generate_identity_and_session() -> None:
    event = RetailEvent.model_validate(_base_event())

    assert event.event_id is not None
    assert event.session_id is not None
    assert event.occurred_at.tzinfo is not None


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RetailEvent.model_validate(
            _base_event(occurred_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )


def test_zone_event_requires_zone_id() -> None:
    with pytest.raises(ValidationError):
        RetailEvent.model_validate(_base_event(event_type=EventType.ZONE_ENTER))


def test_zone_dwell_requires_dwell_seconds() -> None:
    with pytest.raises(ValidationError):
        RetailEvent.model_validate(
            _base_event(event_type=EventType.ZONE_DWELL, zone_id="aisle-03")
        )


def test_queue_event_requires_queue_depth() -> None:
    with pytest.raises(ValidationError):
        RetailEvent.model_validate(
            _base_event(event_type=EventType.BILLING_QUEUE_JOIN, zone_id="billing")
        )


def test_queue_event_accepts_valid_queue_depth() -> None:
    event = RetailEvent.model_validate(
        _base_event(
            event_type=EventType.BILLING_QUEUE_JOIN,
            zone_id="billing",
            metadata=EventMetadata(queue_depth=4),
        )
    )

    assert event.metadata.queue_depth == 4


def test_simulator_generates_expected_retail_scenarios() -> None:
    simulator = RetailEventSimulator(
        SimulationProfile(store_id=uuid4(), seed=7, start_at=datetime(2026, 1, 1, tzinfo=UTC))
    )

    events = simulator.generate_batch()
    event_types = {event.event_type for event in events}
    scenarios = {event.metadata.scenario for event in events}

    assert EventType.ENTRY in event_types
    assert EventType.REENTRY in event_types
    assert EventType.BILLING_QUEUE_ABANDON in event_types
    assert EventType.ZONE_DWELL in event_types
    assert "staff_movement" in scenarios
    assert "partial_occlusion" in scenarios
    assert "queue_buildup" in scenarios
    assert "overlapping_cameras" in scenarios


def test_simulator_sequence_numbers_are_monotonic() -> None:
    simulator = RetailEventSimulator(
        SimulationProfile(store_id=uuid4(), seed=1, start_at=datetime(2026, 1, 1, tzinfo=UTC))
    )

    sequence_numbers = [event.sequence_number for event in simulator.generate_batch()]

    assert sequence_numbers == sorted(sequence_numbers)
    assert len(sequence_numbers) == len(set(sequence_numbers))


def test_simulator_models_confidence_drop_for_occlusion() -> None:
    simulator = RetailEventSimulator(
        SimulationProfile(store_id=uuid4(), seed=3, start_at=datetime(2026, 1, 1, tzinfo=UTC))
    )

    occlusion_events = [
        event
        for event in simulator.generate_batch()
        if event.metadata.scenario == "partial_occlusion"
    ]

    assert min(event.confidence for event in occlusion_events) < 0.5
    assert any(event.metadata.occlusion_ratio for event in occlusion_events)


def test_simulator_marks_staff_separately_from_customers() -> None:
    simulator = RetailEventSimulator(
        SimulationProfile(store_id=uuid4(), seed=4, start_at=datetime(2026, 1, 1, tzinfo=UTC))
    )

    staff_events = [
        event
        for event in simulator.generate_batch()
        if event.metadata.scenario == "staff_movement"
    ]

    assert staff_events
    assert {event.person_type for event in staff_events} == {"STAFF"}


@pytest.mark.asyncio
async def test_mock_cv_adapters_share_pipeline_contracts() -> None:
    frame = VideoFrame(
        frame_id=0,
        camera_id="entrance-cam-01",
        timestamp_ms=0,
        image=object(),
    )

    detections = await MockDetector().detect(frame)
    tracks = await MockTracker().update(frame, detections)
    identity = await MockReID().identify(frame, tracks[0])
    zone_state = await MockZoneResolver().resolve(tracks[0])

    assert detections[0].class_name == "person"
    assert tracks[0].track_id.startswith("entrance-cam-01-track")
    assert identity.global_person_id
    assert zone_state.zone_id == "entrance"
