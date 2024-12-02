import json

from fastapi import WebSocketDisconnect, WebSocketException

from .auth import verify_token
from database.mangodb import mango_sessionmanager
from message.mangomodel import Message, ChatRoom
from bson import ObjectId
from bson.errors import InvalidId
from .schema import (
    WebsocketRecievedMessage, WebSocketResponse
)

main_connections = {}

connections = {}


class RoomManager:
    def __init__(self, room_name):
        self.room = room_name
        self.connected_users = {}
        self.room_users = []

    @classmethod
    async def connect(
            cls, websocket, room_id
    ):
        await websocket.accept()
        room = await cls.check_room(room_id)
        if not room:
            return None, None
        try:
            token = await websocket.receive_text()
            user_id = verify_token(token)

            if room_id in connections:
                connections[room_id].connected_users[user_id] = websocket
            else:
                new_room = cls(room_id)
                new_room.room_users = [usr.user_id for usr in room.users]
                new_room.connected_users[user_id] = websocket
                connections[room_id] = new_room

            return connections[room_id], user_id

        except (WebSocketDisconnect, WebSocketException):
            print("websocket is disconnected")
            return None, None

    def disconnect(self, user_id):
        del self.connected_users[user_id]
        if not self.connected_users:
            self.delete_room()

    async def close_room(self):
        for websocket in self.connected_users.values():
            await websocket.close()
        self.delete_room()

    def delete_room(self):
        if self.room in connections:
            del connections[self.room]

    async def handle_msg(self, data):
        msg = WebsocketRecievedMessage(**(json.loads(data)))
        print(msg.model_dump_json())

        if msg.event_type == "new_msg":
            message = await self.save_new_message({
                "room_id": msg.room_id,
                "message_text": msg.data.message_text,
                "sender_id": msg.sender_id
            })
            await self.broadcast([message], msg.event_type, msg.sender_user)

        elif msg.event_type == "change_msg_status":
            message = await self.change_msg_status(
                msg.data.message_id_list, msg.data.status, msg.sender_id
            )
            await self.broadcast(message, msg.event_type, msg.sender_user)

    async def broadcast(
            self, msg, event_type, sender_user
    ):
        msg_response = WebSocketResponse(
            event_type=event_type, msg=msg, sender_user=sender_user
        )

        # send a msg to online user who not connected in room.
        for user in [
            usr for usr in self.room_users if usr not in self.connected_users.keys()
        ]:
            if int(user) in main_connections.keys():
                await main_connections[user].send_msg(msg_response)

        for websocket in self.connected_users.values():
            await websocket.send_text(msg_response.model_dump_json())

    @staticmethod
    async def save_new_message(msg):
        async with mango_sessionmanager.engine.session() as mangodb:
            message = Message(**msg)
            await mangodb.save(message)
            return message

    @staticmethod
    async def change_msg_status(
            msg_id_list, msg_status, sender_user
    ):
        msg_object_id_list = [ObjectId(msg_id) for msg_id in msg_id_list]
        async with mango_sessionmanager.engine.session() as mangodb:
            messages = await mangodb.find(Message, Message.id.in_(msg_object_id_list))
            for msg in messages:
                if msg.sender_id != sender_user.id or msg_status == "delivered":
                    msg.status = msg_status

            await mangodb.save_all(messages)

            return messages

    @staticmethod
    async def check_room(room_id):
        try:
            room_object_id = ObjectId(room_id)
        except InvalidId:
            return None
        async with mango_sessionmanager.engine.session() as mangodb:
            room = await mangodb.find_one(ChatRoom, ChatRoom.id == room_object_id)
            return room if room.is_active else None
