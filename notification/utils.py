from account.schemas import UserModel
from notification.schemas import NotificationModel
from websocket.manager.connections import main_connections
from notification.models import Notification
from account.models import User


async def send_notification_to_user(notification: Notification, sender_user: User):
    if notification.receiver_id in main_connections:
        await main_connections[notification.receiver_id].send_notification(
            NotificationModel(**notification.__dict__),
            sender_user=UserModel(**sender_user.__dict__),
        )
        return True

    return False
