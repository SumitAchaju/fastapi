from pydantic import BaseModel, field_validator

from message.mangomodel import Message
from notification.schemas import NotificationModel

valid_operation = ("new_msg", "change_msg_status")


class WebsocketMsgResponse(BaseModel):
    msg_type: str
    msg: list[Message]


class WebsocketNotificationResponse(BaseModel):
    msg_type: str = "notification"
    msg: NotificationModel


class WebsocketMsg(BaseModel):
    type: str
    room_id: str
    status: str
    sender_id: int
    message_text: str | None
    messages: list["RecievedMsg"] | None

    @field_validator("type")
    @classmethod
    def validate_msg_type(cls, v: str):
        if v not in valid_operation:
            raise ValueError(f"msg type must be in {valid_operation}")
        return v


class RecievedMsg(BaseModel):
    id: str
    message_text: str
    created_at: str
    message_type: str
    file_links: list[str] | None
    status: str
    seen_by: list[int]


class MainWebsocketMsg(WebsocketMsg):
    reciever_id: int
