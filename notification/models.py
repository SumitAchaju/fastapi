from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from account.models import User

from database.base import Base
from message.mangomodel import formated_date


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column(default=formated_date())
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str]
    title: Mapped[str]
    message: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True, nullable=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    is_canceled: Mapped[bool] = mapped_column(default=False, nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
