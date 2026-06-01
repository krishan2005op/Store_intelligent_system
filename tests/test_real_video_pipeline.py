# PROMPT:
# Build a production-grade Store Intelligence Platform skeleton before dataset arrival.
#
# CHANGES MADE:
# Added real-video MVP tests for OpenCV frame reading, CPU fallback detection, camera-role
# event generation, and JSONL event output using a synthetic MP4.

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import cv2
import numpy as np
import pytest

from app.core.dataset_config import CameraProfile, CameraRole, StoreDatasetProfile
from pipeline.config import PipelineSettings
from pipeline.dataset_runner import DatasetVideoPipeline, load_events_from_jsonl
from pipeline.detect import OpenCVMotionPersonDetector, VideoFrame
from pipeline.event_builder import RetailEventBuilder
from pipeline.schemas import EventType, PersonType
from pipeline.video import OpenCVVideoSource


STORE_UUID = "00000000-0000-4000-8000-000000009999"


def _write_synthetic_video(path: Path) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        10.0,
        (320, 240),
    )
    for index in range(30):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        x = 30 + index * 4
        cv2.rectangle(frame, (x, 60), (x + 38, 180), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()


def test_opencv_video_source_reads_metadata_and_frames(tmp_path: Path) -> None:
    video_path = tmp_path / "CAM 1.mp4"
    _write_synthetic_video(video_path)
    source = OpenCVVideoSource(video_path, "CAM 1")

    metadata = source.metadata()
    frames = list(source.iter_frames(frame_stride=5, max_frames=3))

    assert metadata.width == 320
    assert metadata.height == 240
    assert metadata.frame_count > 0
    assert len(frames) == 3
    assert frames[0].camera_id == "CAM 1"


@pytest.mark.asyncio
async def test_opencv_motion_detector_detects_moving_person_like_region() -> None:
    detector = OpenCVMotionPersonDetector(min_area=300, min_confidence=0.35)
    detections = []
    for index in range(6):
        frame_image = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.rectangle(frame_image, (40 + index * 16, 60), (80 + index * 16, 180), (255, 255, 255), -1)
        detections = await detector.detect(
            VideoFrame(
                frame_id=index,
                camera_id="CAM 1",
                timestamp_ms=index * 100,
                image=frame_image,
            )
        )

    assert detections
    assert detections[0].class_name == "person"


def test_event_builder_maps_camera_roles_to_retail_events() -> None:
    builder = RetailEventBuilder(
        store_id=UUID(STORE_UUID),
        base_time=datetime(2026, 4, 10, tzinfo=UTC),
    )
    frame = VideoFrame(frame_id=1, camera_id="CAM 5", timestamp_ms=1000, image=object())
    from pipeline.detect import Detection
    from pipeline.schemas import BoundingBox

    events = builder.build_events(
        frame=frame,
        detections=[
            Detection(
                detection_id="det-1",
                class_name="person",
                confidence=0.8,
                bbox=BoundingBox(x=1, y=2, width=30, height=80),
            )
        ],
        camera=CameraProfile(
            camera_id="CAM 5",
            source_file="CAM 5.mp4",
            role=CameraRole.BILLING,
            description="billing",
        ),
        sequence_start=1,
    )

    assert events[0].event_type == EventType.BILLING_QUEUE_JOIN
    assert events[0].zone_id == "billing"
    assert events[0].person_type == PersonType.CUSTOMER
    assert events[0].metadata.queue_depth == 1


@pytest.mark.asyncio
async def test_dataset_video_pipeline_writes_jsonl_events(tmp_path: Path) -> None:
    video_path = tmp_path / "CAM 1.mp4"
    output_path = tmp_path / "events.jsonl"
    _write_synthetic_video(video_path)

    profile = StoreDatasetProfile(
        external_store_id="TEST",
        store_name="Synthetic_Test_Store",
        city="Test",
        canonical_store_uuid=STORE_UUID,
        pos_date="10-04-2026",
        cameras=(
            CameraProfile(
                camera_id="CAM 1",
                source_file="CAM 1.mp4",
                role=CameraRole.SALES_FLOOR,
                description="synthetic sales floor",
            ),
        ),
    )
    settings = PipelineSettings(
        app=object(),  # type: ignore[arg-type]
        detector_backend="opencv_motion",
        tracker_backend="mock",
        reid_backend="mock",
        model_path=None,
        device="cpu",
        min_detection_confidence=0.35,
        frame_stride=3,
        max_frames_per_camera=10,
    )

    result = await DatasetVideoPipeline(
        dataset_dir=tmp_path,
        output_path=output_path,
        settings=settings,
        profile=profile,
    ).run()
    events = load_events_from_jsonl(output_path)

    assert result.event_count == len(events)
    assert result.event_count > 0
    assert {event.event_type for event in events} == {EventType.ZONE_DWELL}
