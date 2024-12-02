import json
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from websocket.auth import verify_token
from .schema import (
    WebsocketRecievedMessage, WebSocketResponse
)
from .room_manager import RoomManager, main_connections


class MainConnectionManager:
    def __init__(self, websocket: WebSocket, user_id: int) -> None:
        self.websocket = websocket
        self.user_id = user_id

    @classmethod
    async def connect(cls, websocket: WebSocket) -> Optional["MainConnectionManager"]:
        await websocket.accept()
        try:
            token = await websocket.receive_text()
            user_id = verify_token(token)
            con = cls(websocket, user_id)
            main_connections[user_id] = con
            return con
        except WebSocketDisconnect:
            print("websocket is disconnected")
            return None

    def disconnect(self):
        main_connections.pop(self.user_id, None)

    async def send_msg(self, msg: WebSocketResponse):
        await self.websocket.send_text(msg.model_dump_json())

    @staticmethod
    async def handle_msg(data: str):
        msg = WebsocketRecievedMessage(**(json.loads(data)))
        if msg.event_type == "change_msg_status":
            messages = await RoomManager.change_msg_status(
                msg.data.message_id_list, msg.data.status, msg.sender_id
            )
            msg_response = WebSocketResponse(
                event_type=msg.event_type, data=messages, sender_user=msg.sender_user
            )
            for message in messages:
                if message.sender_id in main_connections:
                    await main_connections[message.sender_id].send_msg(msg_response)
