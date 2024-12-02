from typing import Union, Literal

from pydantic import BaseModel, model_validator

from message.mangomodel import Message
from notification.schemas import NotificationModel
from account.schemas import UserModel

type EventType = Literal["new_message", "change_message_status", "notification"]


class WebSocketResponse(BaseModel):
    event_type: EventType
    data: list[Message] | list[NotificationModel]
    sender_user: UserModel

    @model_validator(mode="after")
    def validate_data_type(self):
        if self.event_type == "notification":
            if not all(isinstance(item, NotificationModel) for item in self.data):
                raise ValueError(
                    "Data must be a list of NotificationModel for 'notification' event_type"
                )
        elif self.event_type in ("new_message", "change_message_status"):
            if not all(isinstance(item, Message) for item in self.data):
                raise ValueError(
                    "Data must be a list of Message for 'new_message' or 'change_message_status' event_type"
                )

        return self


class WebsocketRecievedMessage(BaseModel):
    event_type: EventType
    room_id: str
    data: Union["NewMessageEvent", "ChangeMessageStatusEvent"]
    sender_user: UserModel

    @model_validator(mode="after")
    def validate_data_type(self):
        if self.event_type == "new_message":
            if not isinstance(self.data, NewMessageEvent):
                raise ValueError(
                    "Data must be a NewMessageEvent for 'new_message' event_type"
                )
        elif self.event_type == "change_message_status":
            if not isinstance(self.data, ChangeMessageStatusEvent):
                raise ValueError(
                    "Data must be a ChangeMessageStatusEvent for 'change_message_status' event_type"
                )

        return self


class NewMessageEvent(BaseModel):
    message_text: str


class ChangeMessageStatusEvent(BaseModel):
    message_id_list: list[str]
    status: str
