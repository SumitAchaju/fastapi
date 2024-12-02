import enum

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import ENUM as PGENUM
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship

from account.models import User
from database.base import Base
from message.mangomodel import formated_date
from sqlalchemy.ext.mutable import MutableDict


class NotificationType(enum.Enum):
    FRIEND_REQUEST = "friend_request"
    FRIEND_REQUEST_ACCEPTED = "friend_request_accepted"
    FRIEND_REQUEST_REJECTED = "friend_request_rejected"
    FRIEND_REQUEST_CANCELED = "friend_request_canceled"
    BLOCK_FRIEND = "block_friend"
    UNBLOCK_FRIEND = "unblock_friend"
    UNFRIEND = "unfriend"


json_data_friend_request = {
    "is_active": True,
    "is_canceled": False,
    "is_accepted": False,
    "is_rejected": False,
}


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column(default=formated_date())
    read_at: Mapped[str] = mapped_column(default=None, nullable=True)
    notification_type: Mapped[NotificationType] = mapped_column(
        PGENUM(NotificationType, name="notification_type"),
        default=NotificationType.FRIEND_REQUEST,
    )
    message: Mapped[str]
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    extra_data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default={})

    linked_notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), nullable=True
    )

    sender_user: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    receiver_user: Mapped["User"] = relationship("User", foreign_keys=[receiver_id])
    linked_notification: Mapped["Notification"] = relationship(
        "Notification",
        remote_side=[id],
        backref="parent_notification",
        lazy="joined",
    )
