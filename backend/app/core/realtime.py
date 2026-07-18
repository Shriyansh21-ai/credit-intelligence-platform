import asyncio
from typing import List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        if not self.active:
            return
        living: List[WebSocket] = []
        for ws in list(self.active):
            try:
                await ws.send_json(message)
                living.append(ws)
            except Exception:
                try:
                    asyncio.create_task(ws.close())
                finally:
                    # drop connection
                    pass
        self.active = living


manager = ConnectionManager()
