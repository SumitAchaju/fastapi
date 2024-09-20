from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .manager import RoomManager, MainConnectionManager
from message.mangomodel import ChatRoom
from database.mangodb import mangodb_dependency
from .manager import connections
from fastapi.websockets import WebSocketState

router = APIRouter(prefix="/ws", tags=["ws"])


@router.websocket("/")
async def websocket_main(websocket: WebSocket):
    con = await MainConnectionManager.connect(websocket)

    if con is not None:
        try:
            while True:
                data = await websocket.receive_text()
                await con.handle_msg(data)
        except WebSocketDisconnect:
            print("main websocket has been closed")
            con.disconnect()
    else:
        print("main socket closed with out validation")
        if websocket.application_state != WebSocketState.DISCONNECTED:
            await websocket.close()


@router.websocket("/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    room, user_id = await RoomManager.connect(websocket, room_id)
    if room is not None and user_id is not None:
        try:
            while True:
                data = await websocket.receive_text()
                await room.handle_msg(data)
        except WebSocketDisconnect:
            print("websocket has been closed")
            room.disconnect(user_id)
    else:
        print("room socket closed with out validation")
        if websocket.application_state != WebSocketState.DISCONNECTED:
            await websocket.close()


@router.get("/connection")
async def get_connections():
    result = []
    for con in connections.values():
        for key in con.connected_users.keys():
            result.append(str(key))
    return result
