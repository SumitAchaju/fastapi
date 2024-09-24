import json
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect, WebSocketException

from websocket.auth import verify_token
from database.mangodb import mango_sessionmanager
from message.mangomodel import Message, ChatRoom
from bson import ObjectId
from bson.errors import InvalidId
from .schema import (
    WebsocketMsgResponse,
    WebsocketMsg,
    RecievedMsg,
    MainWebsocketMsg,
    WebsocketNotificationResponse,
)

from notification.schemas import NotificationModel, UserModel

main_connections: dict[str, "MainConnectionManager"] = {}
connections: dict[str, "RoomManager"] = {}


class MainConnectionManager:
    def __init__(self, websocket: WebSocket, user_id: str) -> None:
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

    async def send_msg(self, msg: WebsocketMsgResponse):
        await self.websocket.send_json(msg.model_dump_json())

    async def handle_msg(self, data: str):
        msg = MainWebsocketMsg(**(json.loads(data)))
        if msg.reciever_id in main_connections:
            messages = await RoomManager.change_msg_status(
                msg.messages, msg.status, msg.sender_id
            )
            msg_response = WebsocketMsgResponse(
                msg_type="change_msg_status", msg=messages, sender_user=msg.sender_user
            )
            await main_connections[msg.reciever_id].send_msg(msg_response)

    async def send_notification(self, msg: NotificationModel, sender_user: UserModel):
        msg_response = WebsocketNotificationResponse(msg=msg, sender_user=sender_user)
        await self.send_msg(msg_response)


class RoomManager:
    def __init__(self, room_name: str):
        self.room = room_name
        self.connected_users: dict[str, WebSocket] = {}
        self.room_users: list[int] = []
        self.closed = False

    @classmethod
    async def connect(
        cls, websocket: WebSocket, room_id: str
    ) -> tuple["RoomManager", str] | tuple[None, None]:
        await websocket.accept()
        room = await cls.check_room(room_id)
        if not room:
            return (None, None)
        try:
            token = await websocket.receive_text()
            user_id = verify_token(token)

            if room_id in connections:
                connections[room_id].connected_users[user_id] = websocket
            else:
                newRoom = cls(room_id)
                newRoom.room_users = [usr.user_id for usr in room.users]
                newRoom.connected_users[user_id] = websocket
                connections[room_id] = newRoom

            return connections[room_id], user_id

        except (WebSocketDisconnect, WebSocketException):
            print("websocket is disconnected")
            return (None, None)

    def set_closed(self):
        self.closed = True

    def disconnect(self, user_id: str):
        del self.connected_users[user_id]
        if len(self.connected_users) == 0:
            del connections[self.room]

    async def handle_msg(self, data: str):
        msg = WebsocketMsg(**(json.loads(data)))
        if self.closed:
            raise WebSocketDisconnect()

        if msg.type == "new_msg":
            message = await self.save_message(msg)
            await self.broadcast(message, msg.type, msg.sender_user)
            return

        elif msg.type == "change_msg_status":
            message = await self.change_msg_status(
                msg.messages, msg.status, msg.sender_id
            )
            await self.broadcast(message, msg.type, msg.sender_user)

    async def broadcast(
        self, msg: list[Message], msg_type: str, sender_user: UserModel
    ):
        msg_response = WebsocketMsgResponse(
            msg_type=msg_type, msg=msg, sender_user=sender_user
        )

        # send msg to online user who are not connected in room
        for user in [
            usr for usr in self.room_users if usr not in self.connected_users.keys()
        ]:
            if user in main_connections.keys():
                await main_connections[user].send_msg(msg_response)

        for websocket in self.connected_users.values():
            await websocket.send_json(msg_response.model_dump_json())

    @staticmethod
    async def save_message(msg: WebsocketMsg):
        async with mango_sessionmanager.engine.session() as mangodb:
            message = Message(**msg.model_dump())
            await mangodb.save(message)
            return [message]

    @staticmethod
    async def change_msg_status(
        msg_list: list[RecievedMsg] | None, msg_status: str, sender_id: int
    ):
        if msg_list is None:
            return
        msg_id_list = [ObjectId(msg.id) for msg in msg_list if msg.status != msg_status]
        async with mango_sessionmanager.engine.session() as mangodb:
            messages = await mangodb.find(Message, Message.id.in_(msg_id_list))
            for msg in messages:
                if msg.sender_id != sender_id or msg_status == "delivered":
                    msg.status = msg_status

            await mangodb.save_all(messages)

            return messages

    @staticmethod
    async def check_room(room_id: str) -> ChatRoom | None:
        try:
            room_object_id = ObjectId(room_id)
        except InvalidId:
            return None
        async with mango_sessionmanager.engine.session() as mangodb:
            room = await mangodb.find_one(ChatRoom, ChatRoom.id == room_object_id)
            if not room.is_active:
                return None
            return room
