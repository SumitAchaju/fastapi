import json
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from account.schemas import UserModel
from message.utils import change_msg_status
from notification.schemas import NotificationModel
from websocket.auth import verify_token
from websocket.schema import WebsocketRecievedMessage, WebSocketResponse
from .connections import main_connections


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

    def disconnect(self) -> None:
        main_connections.pop(self.user_id, None)

    async def send_msg(self, msg: WebSocketResponse) -> None:
        await self.websocket.send_text(msg.model_dump_json())

    @staticmethod
    async def handle_msg(data: str):
        try:
            msg = WebsocketRecievedMessage(**(json.loads(data)))
        except ValueError as e:
            print(e.__traceback__)
            return None

        if msg.event_type == "change_message_status":
            messages = await change_msg_status(
                msg.data.message_id_list, msg.data.status, msg.sender_user.id
            )
            msg_response = WebSocketResponse(
                event_type=msg.event_type, data=messages, sender_user=msg.sender_user
            )
            for message in messages:
                if message.sender_id in main_connections:
                    await main_connections[message.sender_id].send_msg(msg_response)

    async def send_notification(
        self, notification: NotificationModel, sender_user: UserModel
    ):
        notification_data = WebSocketResponse(
            event_type="notification", data=[notification], sender_user=sender_user
        )
        await self.send_msg(notification_data)
