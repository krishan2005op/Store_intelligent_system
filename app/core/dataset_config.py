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


STORE_1_PROFILE = StoreDatasetProfile(
    external_store_id="ST1008",
    store_name="Store_1",
    city="Bangalore",
    canonical_store_uuid="00000000-0000-4000-8000-000000001008",
    pos_date="10-04-2026",
    cameras=(
        CameraProfile(
            camera_id="CAM 1",
            source_file="CAM 1 - zone.mp4",
            role=CameraRole.SALES_FLOOR,
            description="Store 1 sales floor zone camera.",
        ),
        CameraProfile(
            camera_id="CAM 2",
            source_file="CAM 2 - zone.mp4",
            role=CameraRole.SALES_FLOOR,
            description="Store 1 secondary sales floor zone camera.",
        ),
        CameraProfile(
            camera_id="CAM 3",
            source_file="CAM 3 - entry.mp4",
            role=CameraRole.ENTRANCE,
            description="Store 1 entrance camera.",
        ),
        CameraProfile(
            camera_id="CAM 5",
            source_file="CAM 5 - billing.mp4",
            role=CameraRole.BILLING,
            description="Store 1 billing/cash counter camera.",
        ),
    ),
)


STORE_2_PROFILE = StoreDatasetProfile(
    external_store_id="ST1076",
    store_name="Store_2",
    city="Bangalore",
    canonical_store_uuid="00000000-0000-4000-8000-000000001076",
    pos_date="08-03-2026",
    cameras=(
        CameraProfile(
            camera_id="ENTRY 1",
            source_file="entry 1.mp4",
            role=CameraRole.ENTRANCE,
            description="Store 2 primary entrance camera.",
        ),
        CameraProfile(
            camera_id="ENTRY 2",
            source_file="entry 2.mp4",
            role=CameraRole.ENTRANCE,
            description="Store 2 secondary entrance camera for overlap/re-entry checks.",
        ),
        CameraProfile(
            camera_id="ZONE",
            source_file="zone.mp4",
            role=CameraRole.SALES_FLOOR,
            description="Store 2 sales floor and shelf-zone camera.",
        ),
        CameraProfile(
            camera_id="BILLING",
            source_file="billing_area.mp4",
            role=CameraRole.BILLING,
            description="Store 2 billing queue camera.",
        ),
    ),
)


DATASET_PROFILES: dict[str, StoreDatasetProfile] = {
    "store1": STORE_1_PROFILE,
    "store_1": STORE_1_PROFILE,
    "st1008": STORE_1_PROFILE,
    "store2": STORE_2_PROFILE,
    "store_2": STORE_2_PROFILE,
    "st1076": STORE_2_PROFILE,
}


def get_dataset_profile(profile_key: str) -> StoreDatasetProfile:
    normalized_key = profile_key.strip().lower()
    if normalized_key not in DATASET_PROFILES:
        valid_keys = ", ".join(sorted(DATASET_PROFILES))
        raise ValueError(f"Unknown dataset profile '{profile_key}'. Valid profiles: {valid_keys}")
    return DATASET_PROFILES[normalized_key]


# Backward-compatible alias for earlier challenge commands/docs.
BRIGADE_BANGALORE_PROFILE = STORE_1_PROFILE
