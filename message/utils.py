from typing import TypedDict

from bson import ObjectId

from account.schemas import UserModel
from database.mangodb import mango_sessionmanager
from message.mangomodel import Message


NewMessageDataType = TypedDict(
    "NewMessageDataType", {"room_id": str, "message_text": str, "sender_id": int}
)


async def save_new_message(msg: NewMessageDataType):
    async with mango_sessionmanager.engine.session() as mangodb:
        message = Message(**msg)
        await mangodb.save(message)
        return message


async def change_msg_status(
    msg_id_list: list[str], msg_status: str, sender_user_id: int
) -> list[Message]:
    msg_object_id_list = [ObjectId(msg_id) for msg_id in msg_id_list]
    async with mango_sessionmanager.engine.session() as mangodb:
        messages = await mangodb.find(Message, Message.id.in_(msg_object_id_list))
        print("hello")
        for msg in messages:
            if msg.sender_id != sender_user_id:
                msg.status = msg_status

        await mangodb.save_all(messages)

        return messages
