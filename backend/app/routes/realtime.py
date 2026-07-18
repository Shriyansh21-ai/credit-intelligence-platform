from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.core.realtime import manager

router = APIRouter()


@router.websocket("/ws/predictions")
async def websocket_predictions(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # keep connection alive; clients may send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
