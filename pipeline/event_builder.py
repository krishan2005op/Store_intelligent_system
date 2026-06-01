from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5, NAMESPACE_URL

from app.core.dataset_config import CameraProfile, CameraRole
from pipeline.detect import Detection, VideoFrame
from pipeline.schemas import EventMetadata, EventSource, EventType, PersonType, RetailEvent


@dataclass(slots=True)
class RetailEventBuilder:
    store_id: UUID
    base_time: datetime

    def build_events(
        self,
        *,
        frame: VideoFrame,
        detections: list[Detection],
        camera: CameraProfile,
        sequence_start: int,
    ) -> list[RetailEvent]:
        events: list[RetailEvent] = []
        occurred_at = self.base_time + timedelta(milliseconds=frame.timestamp_ms)
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)

        for index, detection in enumerate(detections, start=1):
            event_type, zone_id, person_type, metadata = self._classify_event(
                camera=camera,
                queue_depth=len(detections),
            )
            identity_key = f"{camera.camera_id}:{frame.frame_id}:{index}"
            session_id = uuid5(NAMESPACE_URL, f"session:{identity_key}")
            events.append(
                RetailEvent(
                    event_id=uuid5(NAMESPACE_URL, f"event:{identity_key}:{event_type}"),
                    store_id=self.store_id,
                    camera_id=camera.camera_id,
                    event_type=event_type,
                    occurred_at=occurred_at,
                    source=EventSource.REALTIME_PIPELINE,
                    confidence=detection.confidence,
                    sequence_number=sequence_start + index - 1,
                    session_id=session_id,
                    track_id=detection.detection_id,
                    global_person_id=f"{camera.camera_id}-person-{index}",
                    person_type=person_type,
                    zone_id=zone_id,
                    bbox=detection.bbox,
                    metadata=metadata,
                )
            )
        return events

    @staticmethod
    def _classify_event(
        *,
        camera: CameraProfile,
        queue_depth: int,
    ) -> tuple[EventType, str | None, PersonType, EventMetadata]:
        if camera.role == CameraRole.ENTRANCE:
            return (
                EventType.ENTRY,
                "entrance",
                PersonType.CUSTOMER,
                EventMetadata(scenario="real_video_entrance"),
            )
        if camera.role == CameraRole.BILLING:
            return (
                EventType.BILLING_QUEUE_JOIN,
                "billing",
                PersonType.CUSTOMER,
                EventMetadata(
                    scenario="real_video_billing",
                    queue_depth=max(queue_depth, 1),
                ),
            )
        if camera.role == CameraRole.STAFF_BACK_AREA:
            return (
                EventType.ZONE_ENTER,
                "staff-back-area",
                PersonType.STAFF,
                EventMetadata(scenario="real_video_staff_area"),
            )
        return (
            EventType.ZONE_DWELL,
            "sales-floor",
            PersonType.CUSTOMER,
            EventMetadata(
                scenario="real_video_sales_floor",
                dwell_seconds=1.0,
            ),
        )
