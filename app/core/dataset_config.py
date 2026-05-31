from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CameraRole(StrEnum):
    ENTRANCE = "ENTRANCE"
    SALES_FLOOR = "SALES_FLOOR"
    BILLING = "BILLING"
    STAFF_BACK_AREA = "STAFF_BACK_AREA"


@dataclass(frozen=True, slots=True)
class CameraProfile:
    camera_id: str
    source_file: str
    role: CameraRole
    description: str


@dataclass(frozen=True, slots=True)
class StoreDatasetProfile:
    external_store_id: str
    store_name: str
    city: str
    canonical_store_uuid: str
    pos_date: str
    cameras: tuple[CameraProfile, ...]


BRIGADE_BANGALORE_PROFILE = StoreDatasetProfile(
    external_store_id="ST1008",
    store_name="Brigade_Bangalore",
    city="Bangalore",
    canonical_store_uuid="00000000-0000-4000-8000-000000001008",
    pos_date="10-04-2026",
    cameras=(
        CameraProfile(
            camera_id="CAM 1",
            source_file="CAM 1.mp4",
            role=CameraRole.SALES_FLOOR,
            description="Sales floor and product browsing shelves.",
        ),
        CameraProfile(
            camera_id="CAM 2",
            source_file="CAM 2.mp4",
            role=CameraRole.SALES_FLOOR,
            description="Sales floor, cosmetics wall, and browsing area.",
        ),
        CameraProfile(
            camera_id="CAM 3",
            source_file="CAM 3.mp4",
            role=CameraRole.ENTRANCE,
            description="Entrance and exterior threshold.",
        ),
        CameraProfile(
            camera_id="CAM 4",
            source_file="CAM 4.mp4",
            role=CameraRole.STAFF_BACK_AREA,
            description="Back/storage area suitable for staff filtering.",
        ),
        CameraProfile(
            camera_id="CAM 5",
            source_file="CAM 5.mp4",
            role=CameraRole.BILLING,
            description="Billing/cash counter area.",
        ),
    ),
)
