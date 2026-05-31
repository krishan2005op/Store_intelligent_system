from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Literal

from app.core.config import AppSettings, get_settings


DetectorBackend = Literal["mock", "yolov8"]
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


def get_pipeline_settings() -> PipelineSettings:
    app_settings = get_settings()
    simulation_defaults = app_settings.pipeline_mode != "real"

    return PipelineSettings(
        app=app_settings,
        detector_backend="mock" if simulation_defaults else "yolov8",
        tracker_backend="mock" if simulation_defaults else "bytetrack",
        reid_backend="mock" if simulation_defaults else "torchreid",
        model_path=None,
        device="cpu",
        min_detection_confidence=0.35,
    )


def get_simulation_seed() -> int:
    raw_seed = os.getenv("SIMULATION_SEED", "42")
    try:
        return int(raw_seed)
    except ValueError as exc:
        raise ValueError("SIMULATION_SEED must be an integer") from exc
