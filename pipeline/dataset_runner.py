from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from app.core.dataset_config import STORE_1_PROFILE, get_dataset_profile, StoreDatasetProfile
from pipeline.config import PipelineSettings, get_real_video_pipeline_settings
from pipeline.event_builder import RetailEventBuilder
from pipeline.factories import build_detector
from pipeline.schemas import EventMetadata, EventSource, EventType, PersonType, RetailEvent
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
        profile: StoreDatasetProfile = STORE_1_PROFILE,
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
        for sequence_number, line in enumerate(source, start=1):
            if line.strip():
                payload = json.loads(line)
                events.append(_load_event_payload(payload, sequence_number))
    return events


def _load_event_payload(payload: dict[str, Any], sequence_number: int) -> RetailEvent:
    if "event_id" in payload and "occurred_at" in payload:
        return RetailEvent.model_validate(payload)
    return _adapt_external_sample_event(payload, sequence_number)


def _adapt_external_sample_event(payload: dict[str, Any], sequence_number: int) -> RetailEvent:
    external_event_type = str(payload.get("event_type", "")).strip().lower()
    event_type = _map_external_event_type(external_event_type)
    store_id = _canonical_store_uuid(payload)
    occurred_at = _external_event_time(payload)
    identity_key = _external_identity_key(payload)
    zone_id = _external_zone_id(payload, event_type)
    metadata = _external_metadata(payload, external_event_type)
    stable_key = json.dumps(payload, sort_keys=True, default=str)

    return RetailEvent(
        event_id=uuid5(NAMESPACE_URL, f"external-event:{stable_key}"),
        store_id=store_id,
        camera_id=str(payload.get("camera_id") or "unknown-camera"),
        event_type=event_type,
        occurred_at=occurred_at,
        source=EventSource.BATCH_REPLAY,
        confidence=float(payload.get("confidence") or 0.9),
        sequence_number=sequence_number,
        session_id=uuid5(NAMESPACE_URL, f"external-session:{store_id}:{identity_key}"),
        track_id=identity_key,
        global_person_id=identity_key,
        person_type=PersonType.STAFF if payload.get("is_staff") is True else PersonType.CUSTOMER,
        zone_id=zone_id,
        metadata=metadata,
    )


def _map_external_event_type(external_event_type: str) -> EventType:
    event_map = {
        "entry": EventType.ENTRY,
        "exit": EventType.EXIT,
        "zone_entered": EventType.ZONE_ENTER,
        "zone_exited": EventType.ZONE_EXIT,
        "queue_completed": EventType.BILLING_QUEUE_JOIN,
        "queue_abandoned": EventType.BILLING_QUEUE_ABANDON,
    }
    if external_event_type not in event_map:
        raise ValueError(f"Unsupported external event_type '{external_event_type}'")
    return event_map[external_event_type]


def _canonical_store_uuid(payload: dict[str, Any]) -> UUID:
    external_store_id = str(payload.get("store_id") or "").strip().lower()
    store_code = str(payload.get("store_code") or "").strip().lower()
    if external_store_id == "st1008" or store_code == "store_1008":
        return UUID(get_dataset_profile("store1").canonical_store_uuid)
    if external_store_id == "st1076" or store_code == "store_1076":
        return UUID(get_dataset_profile("store2").canonical_store_uuid)
    raise ValueError(f"Cannot map external store identity from payload: {payload}")


def _external_event_time(payload: dict[str, Any]) -> datetime:
    raw_value = (
        payload.get("event_timestamp")
        or payload.get("event_time")
        or payload.get("queue_join_ts")
    )
    if raw_value is None:
        raise ValueError("External sample event is missing a timestamp field")
    parsed = datetime.fromisoformat(str(raw_value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _external_identity_key(payload: dict[str, Any]) -> str:
    identity = (
        payload.get("id_token")
        or payload.get("track_id")
        or payload.get("queue_event_id")
        or payload.get("person_id")
    )
    return str(identity or "anonymous")


def _external_zone_id(payload: dict[str, Any], event_type: EventType) -> str | None:
    zone_id = payload.get("zone_id")
    if zone_id:
        return str(zone_id)
    if event_type in {EventType.BILLING_QUEUE_JOIN, EventType.BILLING_QUEUE_ABANDON}:
        return "billing"
    if event_type in {EventType.ZONE_ENTER, EventType.ZONE_EXIT, EventType.ZONE_DWELL}:
        return "sales-floor"
    return None


def _external_metadata(payload: dict[str, Any], external_event_type: str) -> EventMetadata:
    queue_depth = payload.get("queue_position_at_join")
    metadata: dict[str, Any] = {
        "scenario": "external_sample_dataset",
        "external_event_type": external_event_type,
        "external_store_id": payload.get("store_id") or payload.get("store_code"),
        "zone_name": payload.get("zone_name"),
        "zone_type": payload.get("zone_type"),
        "group_id": payload.get("group_id"),
        "group_size": payload.get("group_size"),
        "gender": payload.get("gender"),
        "age": payload.get("age"),
        "age_bucket": payload.get("age_bucket"),
        "wait_seconds": payload.get("wait_seconds"),
        "queue_served_ts": payload.get("queue_served_ts"),
        "queue_exit_ts": payload.get("queue_exit_ts"),
        "abandoned": payload.get("abandoned"),
    }
    if queue_depth is not None:
        metadata["queue_depth"] = int(queue_depth)
    if external_event_type.startswith("queue_") and "queue_depth" not in metadata:
        metadata["queue_depth"] = 1
    return EventMetadata(**{key: value for key, value in metadata.items() if value is not None})


async def run_dataset_pipeline(
    dataset_dir: Path,
    output_path: Path,
    profile_key: str = "store1",
) -> DatasetPipelineResult:
    return await DatasetVideoPipeline(
        dataset_dir=dataset_dir,
        output_path=output_path,
        settings=get_real_video_pipeline_settings(),
        profile=get_dataset_profile(profile_key),
    ).run()


async def run_brigade_dataset_pipeline(
    dataset_dir: Path,
    output_path: Path,
) -> DatasetPipelineResult:
    return await run_dataset_pipeline(
        dataset_dir=dataset_dir,
        output_path=output_path,
        profile_key="store1",
    )
