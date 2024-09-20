from pydantic import BaseModel
from .mangomodel import ChatRoom
from account.schemas import UserModel
from .mangomodel import Message


class ChatHistoryResponse(BaseModel):
    users: list[UserModel]
    room: ChatRoom
    message: Message | None = None
    quantity: int


class OnlineUserResponse(BaseModel):
    user: UserModel
    room: ChatRoom
