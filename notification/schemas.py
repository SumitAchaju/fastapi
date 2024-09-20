from pydantic import BaseModel
from account.schemas import UserModel


class NotificationModel(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    created_at: str
    read: bool
    request_id: int
    is_active: bool
    user: UserModel
    is_canceled: bool


class NotificationPatchModel(BaseModel):
    read: bool | None = None
    is_active: bool | None = None
