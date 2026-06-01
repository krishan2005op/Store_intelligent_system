from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from pipeline.detect import VideoFrame


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    path: Path
    camera_id: str
    fps: float
    frame_count: int
    width: int
    height: int
    duration_seconds: float


class OpenCVVideoSource:
    def __init__(self, path: Path, camera_id: str) -> None:
        self._path = path
        self._camera_id = camera_id

    def metadata(self) -> VideoMetadata:
        import cv2

        capture = cv2.VideoCapture(str(self._path))
        try:
            if not capture.isOpened():
                raise ValueError(f"Unable to open video: {self._path}")
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            duration_seconds = frame_count / fps if fps > 0 else 0.0
            return VideoMetadata(
                path=self._path,
                camera_id=self._camera_id,
                fps=fps,
                frame_count=frame_count,
                width=width,
                height=height,
                duration_seconds=duration_seconds,
            )
        finally:
            capture.release()

    def iter_frames(
        self,
        *,
        frame_stride: int,
        max_frames: int,
    ) -> Iterator[VideoFrame]:
        import cv2

        if frame_stride <= 0:
            raise ValueError("frame_stride must be greater than zero")
        if max_frames <= 0:
            return

        capture = cv2.VideoCapture(str(self._path))
        emitted = 0
        frame_id = 0
        try:
            if not capture.isOpened():
                raise ValueError(f"Unable to open video: {self._path}")
            while emitted < max_frames:
                ok, image = capture.read()
                if not ok:
                    break
                if frame_id % frame_stride == 0:
                    timestamp_ms = int(capture.get(cv2.CAP_PROP_POS_MSEC) or 0)
                    yield VideoFrame(
                        frame_id=frame_id,
                        camera_id=self._camera_id,
                        timestamp_ms=timestamp_ms,
                        image=image,
                    )
                    emitted += 1
                frame_id += 1
        finally:
            capture.release()
