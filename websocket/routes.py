from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from websocket.manager.main_manager import MainConnectionManager
from websocket.manager.room_manager import RoomManager
from logger import logger

router = APIRouter(prefix="/ws", tags=["ws"])


@router.websocket("/")
async def websocket_main(websocket: WebSocket):
    websocket_user = None
    try:
        con = await MainConnectionManager.connect(websocket)
        websocket_user = con.user_id
        while True:
            data = await websocket.receive_text()
            await con.handle_msg(data)
    except WebSocketDisconnect:
        logger.info(f"user with id {websocket_user} main websocket closed")
    finally:
        if websocket_user:
            MainConnectionManager.disconnect(websocket_user)


@router.websocket("/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    websocket_user = None
    try:
        room, user_id = await RoomManager.connect(websocket, room_id)
        websocket_user = user_id
        while True:
            data = await websocket.receive_text()
            await room.handle_msg(data)
    except WebSocketDisconnect:
        logger.info(f"user with id {websocket_user} room websocket closed")
    finally:
        if websocket_user:
            RoomManager.disconnect(room_id, websocket_user)
