from fastapi import APIRouter, Request, HTTPException

from auth.permission import require_authentication
from database.asyncdb import asyncdb_dependency
from query import NotificationQuery
from .schemas import NotificationModel, NotificationPatchModel

router = APIRouter(prefix="/notification", tags=["message"])


@router.get("/", response_model=list[NotificationModel])
@require_authentication()
async def get_notification(
    request: Request, db: asyncdb_dependency, limit: int = 10, offset: int = 0
):
    results = await NotificationQuery.get_all_by_reciever_id(
        db, request.user.id, True, limit, offset, ("id", "desc")
    )

    return results


@router.patch("/{notification_id}")
@require_authentication()
async def mark_as_read_or_change_active_status(
    request: Request,
    db: asyncdb_dependency,
    notification_id: int,
    data: NotificationPatchModel,
):
    notification = await NotificationQuery(
        db, {"receiver_id": request.user.id, "id": notification_id}
    ).get_one_filter()
    if not notification:
        raise HTTPException(status_code=404, detail="notification not found")

    if data.is_read is not None:
        notification.is_read = data.is_read
    if data.is_active is not None:
        notification.extra_data.update({"is_active": data.is_active})
    await db.commit()
    return {"msg": "notification updated"}


@router.patch("/mark/read/all")
@require_authentication()
async def mark_all_as_read(request: Request, db: asyncdb_dependency):

    notifications = await NotificationQuery(
        db, {"receiver_id": request.user.id, "is_read": False}
    ).get_all_filter()

    if not notifications:
        raise HTTPException(status_code=404, detail="notification not found")
    for notification in notifications:
        notification.is_read = True
    await db.commit()
    return {"msg": "all notification marked as read"}


@router.delete("/delete/{notification_id}")
@require_authentication()
async def delete_notification(
    request: Request, db: asyncdb_dependency, notification_id: int
):
    notification = await NotificationQuery(
        db, {"receiver_id": request.user.id, "id": notification_id}
    ).get_one_filter()
    if not notification:
        raise HTTPException(status_code=404, detail="notification not found")
    print(notification.__dict__)
    await db.delete(notification)
    await db.commit()
    return {"msg": "notification deleted"}


@router.delete("/all/delete")
@require_authentication()
async def delete_all_notification(request: Request, db: asyncdb_dependency):
    notifications = await NotificationQuery.get_all_by_reciever_id(db, request.user.id)
    if not notifications:
        raise HTTPException(status_code=404, detail="notification not found")
    for noti in notifications:
        await db.delete(noti)
    await db.commit()
    return {"msg": "all notification deleted"}
