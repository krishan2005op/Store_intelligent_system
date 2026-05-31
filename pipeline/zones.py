from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pipeline.tracker import Track


class ZoneKind(StrEnum):
    ENTRANCE = "ENTRANCE"
    EXIT = "EXIT"
    AISLE = "AISLE"
    BILLING_QUEUE = "BILLING_QUEUE"
    STAFF_ONLY = "STAFF_ONLY"


@dataclass(frozen=True, slots=True)
class Zone:
    zone_id: str
    kind: ZoneKind
    camera_id: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def contains_track(self, track: Track) -> bool:
        center_x = track.bbox.x + track.bbox.width / 2
        center_y = track.bbox.y + track.bbox.height / 2
        return self.x_min <= center_x <= self.x_max and self.y_min <= center_y <= self.y_max


@dataclass(frozen=True, slots=True)
class ZoneState:
    track_id: str
    zone_id: str | None


class ZoneResolver(Protocol):
    async def resolve(self, track: Track) -> ZoneState:
        """Resolve a track into the current store zone."""


class GeometryZoneResolver:
    def __init__(self, zones: list[Zone]) -> None:
        self._zones = zones

    async def resolve(self, track: Track) -> ZoneState:
        for zone in self._zones:
            if zone.camera_id == track.camera_id and zone.contains_track(track):
                return ZoneState(track_id=track.track_id, zone_id=zone.zone_id)
        return ZoneState(track_id=track.track_id, zone_id=None)


class MockZoneResolver:
    async def resolve(self, track: Track) -> ZoneState:
        if "entrance" in track.camera_id:
            return ZoneState(track_id=track.track_id, zone_id="entrance")
        if "billing" in track.camera_id:
            return ZoneState(track_id=track.track_id, zone_id="billing")
        return ZoneState(track_id=track.track_id, zone_id="sales-floor")
