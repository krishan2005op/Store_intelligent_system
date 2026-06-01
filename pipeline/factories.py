from __future__ import annotations

from pipeline.config import PipelineSettings
from pipeline.detect import Detector, MockDetector, OpenCVMotionPersonDetector, YOLODetector


def build_detector(settings: PipelineSettings) -> Detector:
    if settings.detector_backend == "mock":
        return MockDetector(min_confidence=settings.min_detection_confidence)
    if settings.detector_backend == "opencv_motion":
        return OpenCVMotionPersonDetector(
            min_confidence=settings.min_detection_confidence,
        )
    if settings.detector_backend == "yolov8":
        return YOLODetector(
            model_path=str(settings.model_path) if settings.model_path else None,
            device=settings.device,
            min_confidence=settings.min_detection_confidence,
        )
    raise ValueError(f"Unsupported detector backend: {settings.detector_backend}")
