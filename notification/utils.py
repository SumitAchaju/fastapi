from sqlalchemy.ext.asyncio import AsyncSession

from notification.schemas import NotificationModel, ValidatedNotification

from notification.models import Notification
from account.models import User


def message_request_data(user: User, title: str):
    return {
        "user_id": user.id,
        "type": "message_request",
        "title": title,
        "message": f"{user.first_name} {user.last_name} has {"sent you" if title=="recieved" else "accepted your"} message request",
    }


async def create_notification(db: AsyncSession, **kwargs):
    notification_model = ValidatedNotification(**kwargs)
    notification = Notification(**notification_model.model_dump())
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    notification_data = NotificationModel(**notification.__dict__)
    return notification_data
