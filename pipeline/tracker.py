from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pipeline.detect import Detection, VideoFrame
from pipeline.schemas import BoundingBox, Confidence


@dataclass(frozen=True, slots=True)
class Track:
    track_id: str
    camera_id: str
    confidence: Confidence
    bbox: BoundingBox
    age_frames: int = 1
    missed_frames: int = 0


class Tracker(Protocol):
    name: str

    async def update(self, frame: VideoFrame, detections: list[Detection]) -> list[Track]:
        """Update tracked identities for one camera."""


class MockTracker:
    name = "mock-tracker"

    async def update(self, frame: VideoFrame, detections: list[Detection]) -> list[Track]:
        return [
            Track(
                track_id=f"{frame.camera_id}-track-{index + 1}",
                camera_id=frame.camera_id,
                confidence=detection.confidence,
                bbox=detection.bbox,
                age_frames=frame.frame_id + 1,
            )
            for index, detection in enumerate(detections)
        ]


class ByteTrackerWrapper:
    name = "bytetrack"

    def __init__(self) -> None:
        self._tracker_by_camera: dict[str, object] = {}

    async def update(self, frame: VideoFrame, detections: list[Detection]) -> list[Track]:
        # Ultralytics exposes ByteTrack through model.track for real video paths/streams.
        # The adapter is intentionally thin until dataset frame cadence and deployment
        # constraints are known.
        return [
            Track(
                track_id=f"{frame.camera_id}-bytetrack-{index + 1}",
                camera_id=frame.camera_id,
                confidence=detection.confidence,
                bbox=detection.bbox,
            )
            for index, detection in enumerate(detections)
        ]
