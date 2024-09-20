from datetime import datetime
from odmantic import Field, Model
from pydantic import field_validator
from typing import Optional
import pytz

valid_message_type = ["text", "video", "image", "document", "links"]
valid_chatroom_type = ["group", "friend"]
valid_message_status = ["sent", "delivered", "seen"]

datetime_format = "%b %d %Y %I:%M:%S %p"


def formated_date():
    kathmandu_tz = pytz.timezone("Asia/Kathmandu")
    return datetime.now(kathmandu_tz).strftime(datetime_format)


class Message(Model):
    room_id: str
    sender_id: int
    message_text: Optional[str] = None
    message_type: str = Field(default="text")
    created_at: str = Field(default_factory=formated_date)
    file_links: Optional[list[str]] = None
    status: str = Field(default="sent")
    seen_by: list[int] = Field(default=[])

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, v: str):
        if v not in valid_message_type:
            raise ValueError(f"message type must be one of {valid_message_type}")
        return v

    @field_validator("status")
    @classmethod
    def validate_message_status(cls, v: str):
        if v not in valid_message_status:
            raise ValueError(f"message type must be one of {valid_message_status}")
        return v


class RoomUser(Model):
    user_id: int
    added_by: Optional[int] = None
    joined_at: str = Field(default_factory=formated_date)
    isAdmin: bool


class ChatRoom(Model):
    users: list[RoomUser]
    created_at: str = Field(default_factory=formated_date)
    type: str
    created_by: Optional[int] = None
    is_active: bool

    @field_validator("type")
    @classmethod
    def validate_roomtype(cls, v: str):
        if v not in valid_chatroom_type:
            raise ValueError(f"chat room type must be one of {valid_chatroom_type}")
        return v
