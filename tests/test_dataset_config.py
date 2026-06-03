# PROMPT:
# Build a production-grade Store Intelligence Platform skeleton before dataset arrival.
#
# CHANGES MADE:
# Added dataset profile tests for Store 1 and Store 2 camera roles and store mapping
# after receiving the final CCTV, layout, POS, and JSONL sample files.

import pytest

from app.core.dataset_config import CameraRole, STORE_1_PROFILE, STORE_2_PROFILE, get_dataset_profile


def test_store_1_profile_maps_pos_store_identity() -> None:
    assert STORE_1_PROFILE.external_store_id == "ST1008"
    assert STORE_1_PROFILE.store_name == "Store_1"
    assert STORE_1_PROFILE.pos_date == "10-04-2026"


def test_store_1_profile_maps_camera_roles() -> None:
    roles = {
        camera.camera_id: camera.role
        for camera in STORE_1_PROFILE.cameras
    }

    assert roles["CAM 3"] == CameraRole.ENTRANCE
    assert roles["CAM 5"] == CameraRole.BILLING
    assert roles["CAM 1"] == CameraRole.SALES_FLOOR
    assert roles["CAM 2"] == CameraRole.SALES_FLOOR


def test_store_2_profile_maps_sample_jsonl_store_identity() -> None:
    assert STORE_2_PROFILE.external_store_id == "ST1076"
    assert STORE_2_PROFILE.store_name == "Store_2"
    assert STORE_2_PROFILE.pos_date == "08-03-2026"


def test_store_2_profile_maps_camera_roles() -> None:
    roles = {
        camera.camera_id: camera.role
        for camera in STORE_2_PROFILE.cameras
    }

    assert roles["ENTRY 1"] == CameraRole.ENTRANCE
    assert roles["ENTRY 2"] == CameraRole.ENTRANCE
    assert roles["ZONE"] == CameraRole.SALES_FLOOR
    assert roles["BILLING"] == CameraRole.BILLING


def test_dataset_profile_lookup_accepts_store_aliases() -> None:
    assert get_dataset_profile("store1") is STORE_1_PROFILE
    assert get_dataset_profile("ST1076") is STORE_2_PROFILE


def test_dataset_profile_lookup_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="Unknown dataset profile"):
        get_dataset_profile("missing-store")
