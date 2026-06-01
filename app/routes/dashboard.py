from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.core.logging import get_logger
from app.services.websocket_service import manager

logger = get_logger(__name__)
router = APIRouter(tags=["dashboard"])
DASHBOARD_TEMPLATE = Path("dashboard/templates/index.html")


@router.get("/dashboard")
async def get_dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_TEMPLATE)


@router.get("/")
async def get_dashboard_root() -> FileResponse:
    return FileResponse(DASHBOARD_TEMPLATE)


@router.websocket("/stores/{store_id}/live")
async def websocket_endpoint(websocket: WebSocket, store_id: UUID) -> None:
    await manager.connect(store_id, websocket)
    logger.info("websocket_connected", store_id=str(store_id))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(store_id, websocket)
        logger.info("websocket_disconnected", store_id=str(store_id))
    except Exception as exc:
        manager.disconnect(store_id, websocket)
        logger.error(
            "websocket_error",
            store_id=str(store_id),
            error_type=type(exc).__name__,
            message=str(exc),
        )
