import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class RealtimeHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._revision = 0

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "revision": self._revision,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
            )
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> int:
        self._revision += 1
        message = json.dumps(
            {
                "type": event_type,
                "revision": self._revision,
                "payload": payload or {},
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
        async with self._lock:
            clients = list(self._clients)

        stale: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_text(message)
            except Exception:
                stale.append(client)

        if stale:
            async with self._lock:
                for client in stale:
                    self._clients.discard(client)
        return self._revision

    @property
    def revision(self) -> int:
        return self._revision


hub = RealtimeHub()
