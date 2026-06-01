from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Literal

from app.core.config import AppSettings, get_settings


DetectorBackend = Literal["mock", "opencv_motion", "yolov8"]
TrackerBackend = Literal["mock", "bytetrack"]
ReIDBackend = Literal["mock", "torchreid"]


@dataclass(frozen=True, slots=True)
class PipelineSettings:
    app: AppSettings
    detector_backend: DetectorBackend
    tracker_backend: TrackerBackend
    reid_backend: ReIDBackend
    model_path: Path | None
    device: Literal["cpu", "cuda"]
    min_detection_confidence: float
    frame_stride: int
    max_frames_per_camera: int


def get_pipeline_settings() -> PipelineSettings:
    app_settings = get_settings()
    simulation_defaults = app_settings.pipeline_mode != "real"

    return PipelineSettings(
        app=app_settings,
        detector_backend="mock" if simulation_defaults else _detector_backend_from_env(),
        tracker_backend="mock" if simulation_defaults else "bytetrack",
        reid_backend="mock" if simulation_defaults else "torchreid",
        model_path=_path_from_env("YOLO_MODEL_PATH"),
        device="cuda" if os.getenv("PIPELINE_DEVICE", "cpu").lower() == "cuda" else "cpu",
        min_detection_confidence=float(os.getenv("MIN_DETECTION_CONFIDENCE", "0.35")),
        frame_stride=int(os.getenv("PIPELINE_FRAME_STRIDE", "30")),
        max_frames_per_camera=int(os.getenv("PIPELINE_MAX_FRAMES_PER_CAMERA", "120")),
    )


def get_real_video_pipeline_settings() -> PipelineSettings:
    app_settings = get_settings()
    return PipelineSettings(
        app=app_settings,
        detector_backend=_detector_backend_from_env(),
        tracker_backend="bytetrack",
        reid_backend="torchreid",
        model_path=_path_from_env("YOLO_MODEL_PATH"),
        device="cuda" if os.getenv("PIPELINE_DEVICE", "cpu").lower() == "cuda" else "cpu",
        min_detection_confidence=float(os.getenv("MIN_DETECTION_CONFIDENCE", "0.35")),
        frame_stride=int(os.getenv("PIPELINE_FRAME_STRIDE", "30")),
        max_frames_per_camera=int(os.getenv("PIPELINE_MAX_FRAMES_PER_CAMERA", "120")),
    )


def get_simulation_seed() -> int:
    raw_seed = os.getenv("SIMULATION_SEED", "42")
    try:
        return int(raw_seed)
    except ValueError as exc:
        raise ValueError("SIMULATION_SEED must be an integer") from exc


def _detector_backend_from_env() -> DetectorBackend:
    raw_backend = os.getenv("DETECTOR_BACKEND", "opencv_motion").strip().lower()
    if raw_backend not in {"mock", "opencv_motion", "yolov8"}:
        raise ValueError("DETECTOR_BACKEND must be one of mock, opencv_motion, yolov8")
    return raw_backend  # type: ignore[return-value]


def _path_from_env(name: str) -> Path | None:
    value = os.getenv(name)
    if not value:
        return None
    return Path(value)
