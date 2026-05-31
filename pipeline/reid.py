from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pipeline.detect import VideoFrame
from pipeline.schemas import Confidence
from pipeline.tracker import Track


@dataclass(frozen=True, slots=True)
class IdentityMatch:
    global_person_id: str
    confidence: Confidence
    is_staff: bool = False


class ReIDManager(Protocol):
    name: str

    async def identify(self, frame: VideoFrame, track: Track) -> IdentityMatch:
        """Map a camera-local track to a store-level identity."""


class MockReID:
    name = "mock-reid"

    async def identify(self, frame: VideoFrame, track: Track) -> IdentityMatch:
        normalized_track = track.track_id.rsplit("-", maxsplit=1)[-1]
        return IdentityMatch(
            global_person_id=f"person-{normalized_track}",
            confidence=max(0.6, track.confidence - 0.05),
        )


class TorchReIDManager:
    name = "torchreid"

    def __init__(self, model_name: str = "osnet_x1_0", device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._extractor: Any | None = None

    def _load_extractor(self) -> Any:
        if self._extractor is None:
            import torchreid

            self._extractor = torchreid.utils.FeatureExtractor(
                model_name=self._model_name,
                model_path="",
                device=self._device,
            )
        return self._extractor

    async def identify(self, frame: VideoFrame, track: Track) -> IdentityMatch:
        self._load_extractor()
        return IdentityMatch(
            global_person_id=f"{frame.camera_id}:{track.track_id}",
            confidence=max(0.5, track.confidence - 0.1),
        )
