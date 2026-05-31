from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pipeline.schemas import BoundingBox, Confidence


@dataclass(frozen=True, slots=True)
class VideoFrame:
    frame_id: int
    camera_id: str
    timestamp_ms: int
    image: Any


@dataclass(frozen=True, slots=True)
class Detection:
    detection_id: str
    class_name: str
    confidence: Confidence
    bbox: BoundingBox


class Detector(Protocol):
    name: str

    async def detect(self, frame: VideoFrame) -> list[Detection]:
        """Return object detections for one frame."""


class MockDetector:
    name = "mock-detector"

    def __init__(self, min_confidence: float = 0.35) -> None:
        self._min_confidence = min_confidence

    async def detect(self, frame: VideoFrame) -> list[Detection]:
        if frame.image is None:
            return []

        confidence = max(self._min_confidence, 0.82)
        return [
            Detection(
                detection_id=f"{frame.camera_id}-{frame.frame_id}-person-1",
                class_name="person",
                confidence=confidence,
                bbox=BoundingBox(x=120.0, y=80.0, width=48.0, height=160.0),
            )
        ]


class YOLODetector:
    name = "yolov8-detector"

    def __init__(self, model_path: str | None, device: str, min_confidence: float) -> None:
        self._model_path = model_path
        self._device = device
        self._min_confidence = min_confidence
        self._model: Any | None = None

    def _load_model(self) -> Any:
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self._model_path or "yolov8n.pt")
        return self._model

    async def detect(self, frame: VideoFrame) -> list[Detection]:
        model = self._load_model()
        results = model.predict(frame.image, device=self._device, verbose=False)
        detections: list[Detection] = []

        for result in results:
            for index, box in enumerate(result.boxes):
                class_id = int(box.cls[0])
                class_name = result.names[class_id]
                confidence = float(box.conf[0])
                if class_name != "person" or confidence < self._min_confidence:
                    continue

                x1, y1, x2, y2 = [float(value) for value in box.xyxy[0]]
                detections.append(
                    Detection(
                        detection_id=f"{frame.camera_id}-{frame.frame_id}-{index}",
                        class_name=class_name,
                        confidence=confidence,
                        bbox=BoundingBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1),
                    )
                )

        return detections
