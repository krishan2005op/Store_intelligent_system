# PROMPT:
# Build a production-grade Store Intelligence Platform skeleton before dataset arrival.
#
# CHANGES MADE:
# Added dataset profile tests for Brigade Bangalore camera roles and POS/store mapping
# after receiving the real CCTV, layout, and POS files.

from app.core.dataset_config import BRIGADE_BANGALORE_PROFILE, CameraRole


def test_brigade_profile_maps_pos_store_identity() -> None:
    assert BRIGADE_BANGALORE_PROFILE.external_store_id == "ST1008"
    assert BRIGADE_BANGALORE_PROFILE.store_name == "Brigade_Bangalore"
    assert BRIGADE_BANGALORE_PROFILE.pos_date == "10-04-2026"


def test_brigade_profile_maps_camera_roles() -> None:
    roles = {
        camera.camera_id: camera.role
        for camera in BRIGADE_BANGALORE_PROFILE.cameras
    }

    assert roles["CAM 3"] == CameraRole.ENTRANCE
    assert roles["CAM 5"] == CameraRole.BILLING
    assert roles["CAM 4"] == CameraRole.STAFF_BACK_AREA
    assert roles["CAM 1"] == CameraRole.SALES_FLOOR
    assert roles["CAM 2"] == CameraRole.SALES_FLOOR
