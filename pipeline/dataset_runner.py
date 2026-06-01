from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from uuid import UUID

from app.core.dataset_config import BRIGADE_BANGALORE_PROFILE, StoreDatasetProfile
from pipeline.config import PipelineSettings, get_real_video_pipeline_settings
from pipeline.event_builder import RetailEventBuilder
from pipeline.factories import build_detector
from pipeline.schemas import RetailEvent
from pipeline.video import OpenCVVideoSource, VideoMetadata


@dataclass(frozen=True, slots=True)
class DatasetPipelineResult:
    output_path: Path
    event_count: int
    video_metadata: list[VideoMetadata]


class DatasetVideoPipeline:
    def __init__(
        self,
        *,
        dataset_dir: Path,
        output_path: Path,
        settings: PipelineSettings,
        profile: StoreDatasetProfile = BRIGADE_BANGALORE_PROFILE,
    ) -> None:
        self._dataset_dir = dataset_dir
        self._output_path = output_path
        self._settings = settings
        self._profile = profile

    async def run(self) -> DatasetPipelineResult:
        detector = build_detector(self._settings)
        store_id = UUID(self._profile.canonical_store_uuid)
        event_builder = RetailEventBuilder(
            store_id=store_id,
            base_time=datetime(2026, 4, 10, 0, 0, tzinfo=UTC),
        )
        self._output_path.parent.mkdir(parents=True, exist_ok=True)

        sequence_number = 1
        event_count = 0
        metadata: list[VideoMetadata] = []
        with self._output_path.open("w", encoding="utf-8") as output:
            for camera in self._profile.cameras:
                video_path = self._dataset_dir / camera.source_file
                source = OpenCVVideoSource(video_path, camera.camera_id)
                video_metadata = source.metadata()
                metadata.append(video_metadata)
                for frame in source.iter_frames(
                    frame_stride=self._settings.frame_stride,
                    max_frames=self._settings.max_frames_per_camera,
                ):
                    detections = await detector.detect(frame)
                    events = event_builder.build_events(
                        frame=frame,
                        detections=detections,
                        camera=camera,
                        sequence_start=sequence_number,
                    )
                    sequence_number += len(events)
                    event_count += len(events)
                    for event in events:
                        output.write(event.model_dump_json() + "\n")

        return DatasetPipelineResult(
            output_path=self._output_path,
            event_count=event_count,
            video_metadata=metadata,
        )


def load_events_from_jsonl(path: Path) -> list[RetailEvent]:
    events: list[RetailEvent] = []
    if not path.exists():
        return events
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                events.append(RetailEvent.model_validate(json.loads(line)))
    return events


async def run_brigade_dataset_pipeline(
    dataset_dir: Path,
    output_path: Path,
) -> DatasetPipelineResult:
    return await DatasetVideoPipeline(
        dataset_dir=dataset_dir,
        output_path=output_path,
        settings=get_real_video_pipeline_settings(),
    ).run()
