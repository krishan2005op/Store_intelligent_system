from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import random
from uuid import UUID, uuid4

from pipeline.schemas import (
    BoundingBox,
    EventMetadata,
    EventSource,
    EventType,
    PersonType,
    RetailEvent,
)


@dataclass(frozen=True, slots=True)
class SimulationProfile:
    store_id: UUID
    seed: int = 42
    start_at: datetime | None = None
    entrance_camera_id: str = "entrance-cam-01"
    exit_camera_id: str = "exit-cam-01"
    billing_camera_id: str = "billing-cam-01"
    overlap_camera_id: str = "entrance-cam-02"
    base_interval_seconds: int = 5


class RetailEventSimulator:
    def __init__(self, profile: SimulationProfile) -> None:
        self._profile = profile
        self._random = random.Random(profile.seed)
        self._sequence_number = 0
        self._clock = profile.start_at or datetime.now(UTC)
        if self._clock.tzinfo is None:
            self._clock = self._clock.replace(tzinfo=UTC)

    async def stream(self, cycles: int = 1) -> AsyncIterator[RetailEvent]:
        for _ in range(cycles):
            for event in self.generate_batch():
                yield event

    def generate_batch(self) -> list[RetailEvent]:
        events: list[RetailEvent] = []
        events.extend(self._empty_store_period())
        events.extend(self._group_entry(group_size=3))
        events.extend(self._staff_movement())
        events.extend(self._partial_occlusion())
        events.extend(self._queue_buildup())
        events.extend(self._overlapping_camera_reentry())
        return events

    def _empty_store_period(self) -> list[RetailEvent]:
        self._advance(seconds=30)
        return []

    def _group_entry(self, group_size: int) -> list[RetailEvent]:
        session_id = uuid4()
        events: list[RetailEvent] = []
        for index in range(group_size):
            person_id = f"group-a-customer-{index + 1}"
            events.append(
                self._event(
                    event_type=EventType.ENTRY,
                    camera_id=self._profile.entrance_camera_id,
                    session_id=session_id,
                    global_person_id=person_id,
                    track_id=f"entrance-track-{index + 1}",
                    confidence=self._confidence(0.88, 0.98),
                    bbox=self._bbox(index),
                    metadata=EventMetadata(scenario="group_entry"),
                )
            )
            events.append(
                self._event(
                    event_type=EventType.ZONE_ENTER,
                    camera_id=self._profile.entrance_camera_id,
                    session_id=session_id,
                    global_person_id=person_id,
                    track_id=f"entrance-track-{index + 1}",
                    zone_id="sales-floor",
                    confidence=self._confidence(0.84, 0.95),
                    bbox=self._bbox(index, y=180.0),
                    metadata=EventMetadata(scenario="group_entry"),
                )
            )
            self._advance()
        return events

    def _staff_movement(self) -> list[RetailEvent]:
        session_id = uuid4()
        person_id = "staff-associate-01"
        events = [
            self._event(
                event_type=EventType.ZONE_ENTER,
                camera_id="aisle-cam-01",
                session_id=session_id,
                global_person_id=person_id,
                track_id="staff-track-01",
                person_type=PersonType.STAFF,
                zone_id="sales-floor",
                confidence=0.96,
                bbox=BoundingBox(x=340.0, y=110.0, width=46.0, height=155.0),
                metadata=EventMetadata(scenario="staff_movement"),
            ),
            self._event(
                event_type=EventType.ZONE_EXIT,
                camera_id="aisle-cam-01",
                session_id=session_id,
                global_person_id=person_id,
                track_id="staff-track-01",
                person_type=PersonType.STAFF,
                zone_id="sales-floor",
                confidence=0.94,
                bbox=BoundingBox(x=420.0, y=118.0, width=45.0, height=154.0),
                metadata=EventMetadata(scenario="staff_movement"),
            ),
        ]
        self._advance(seconds=10)
        return events

    def _partial_occlusion(self) -> list[RetailEvent]:
        session_id = uuid4()
        person_id = "occluded-customer-01"
        events: list[RetailEvent] = []
        for index, confidence in enumerate([0.86, 0.61, 0.42, 0.74]):
            events.append(
                self._event(
                    event_type=EventType.ZONE_DWELL,
                    camera_id="aisle-cam-02",
                    session_id=session_id,
                    global_person_id=person_id,
                    track_id="occlusion-track-01",
                    zone_id="promo-endcap",
                    confidence=confidence,
                    bbox=self._bbox(index, x=500.0, y=220.0),
                    metadata=EventMetadata(
                        scenario="partial_occlusion",
                        occlusion_ratio=round(1.0 - confidence, 2),
                        dwell_seconds=12.5 + index,
                    ),
                )
            )
            self._advance(seconds=4)
        return events

    def _queue_buildup(self) -> list[RetailEvent]:
        session_ids = [uuid4() for _ in range(5)]
        events: list[RetailEvent] = []
        for index, session_id in enumerate(session_ids):
            queue_depth = index + 1
            events.append(
                self._event(
                    event_type=EventType.BILLING_QUEUE_JOIN,
                    camera_id=self._profile.billing_camera_id,
                    session_id=session_id,
                    global_person_id=f"queue-customer-{queue_depth}",
                    track_id=f"billing-track-{queue_depth}",
                    zone_id="billing",
                    confidence=self._confidence(0.82, 0.94),
                    bbox=self._bbox(index, x=220.0, y=300.0),
                    metadata=EventMetadata(
                        scenario="queue_buildup",
                        queue_depth=queue_depth,
                    ),
                )
            )
            self._advance(seconds=8)

        events.append(
            self._event(
                event_type=EventType.BILLING_QUEUE_ABANDON,
                camera_id=self._profile.billing_camera_id,
                session_id=session_ids[-1],
                global_person_id="queue-customer-5",
                track_id="billing-track-5",
                zone_id="billing",
                confidence=0.79,
                bbox=self._bbox(4, x=260.0, y=330.0),
                metadata=EventMetadata(
                    scenario="queue_buildup",
                    queue_depth=4,
                ),
            )
        )
        self._advance(seconds=5)
        return events

    def _overlapping_camera_reentry(self) -> list[RetailEvent]:
        session_id = uuid4()
        person_id = "returning-customer-01"
        metadata = EventMetadata(
            scenario="overlapping_cameras",
            camera_overlap_group="front-door",
            paired_camera_id=self._profile.overlap_camera_id,
        )
        return [
            self._event(
                event_type=EventType.EXIT,
                camera_id=self._profile.exit_camera_id,
                session_id=session_id,
                global_person_id=person_id,
                track_id="exit-track-01",
                confidence=0.9,
                bbox=BoundingBox(x=80.0, y=90.0, width=44.0, height=150.0),
                metadata=metadata,
            ),
            self._event(
                event_type=EventType.REENTRY,
                camera_id=self._profile.overlap_camera_id,
                session_id=session_id,
                global_person_id=person_id,
                track_id="overlap-track-09",
                confidence=0.83,
                bbox=BoundingBox(x=105.0, y=88.0, width=43.0, height=151.0),
                metadata=metadata,
            ),
        ]

    def _event(
        self,
        *,
        event_type: EventType,
        camera_id: str,
        session_id: UUID,
        global_person_id: str,
        track_id: str,
        confidence: float,
        metadata: EventMetadata,
        person_type: PersonType = PersonType.CUSTOMER,
        zone_id: str | None = None,
        bbox: BoundingBox | None = None,
    ) -> RetailEvent:
        self._sequence_number += 1
        return RetailEvent(
            store_id=self._profile.store_id,
            camera_id=camera_id,
            event_type=event_type,
            occurred_at=self._clock,
            source=EventSource.SIMULATOR,
            confidence=round(confidence, 4),
            sequence_number=self._sequence_number,
            session_id=session_id,
            track_id=track_id,
            global_person_id=global_person_id,
            person_type=person_type,
            zone_id=zone_id,
            bbox=bbox,
            metadata=metadata,
        )

    def _advance(self, seconds: int | None = None) -> None:
        step = seconds if seconds is not None else self._profile.base_interval_seconds
        self._clock = self._clock + timedelta(seconds=step)

    def _confidence(self, low: float, high: float) -> float:
        return self._random.uniform(low, high)

    @staticmethod
    def _bbox(index: int, x: float = 120.0, y: float = 80.0) -> BoundingBox:
        return BoundingBox(
            x=x + index * 42.0,
            y=y + index * 4.0,
            width=46.0,
            height=156.0,
        )


def build_default_simulator(store_id: UUID, seed: int = 42) -> RetailEventSimulator:
    return RetailEventSimulator(SimulationProfile(store_id=store_id, seed=seed))
