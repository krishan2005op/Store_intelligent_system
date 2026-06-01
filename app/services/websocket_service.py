from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket

from pipeline.schemas import RetailEvent


class ConnectionManager:
    def __init__(self) -> None:
        self._active_connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, store_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_connections[store_id].add(websocket)

    def disconnect(self, store_id: UUID, websocket: WebSocket) -> None:
        self._active_connections[store_id].discard(websocket)
        if not self._active_connections[store_id]:
            self._active_connections.pop(store_id, None)

    async def broadcast_events(self, store_id: UUID, events: list[RetailEvent]) -> None:
        connections = self._active_connections.get(store_id)
        if not connections:
            return

        payload = {
            "store_id": str(store_id),
            "events": [event.model_dump(mode="json") for event in events],
        }

        dead_connections: list[WebSocket] = []
        for connection in connections:
            try:
                await connection.send_json(payload)
            except Exception:
                dead_connections.append(connection)

        # Cleanup disconnected sockets
        for connection in dead_connections:
            self.disconnect(store_id, connection)


manager = ConnectionManager()
