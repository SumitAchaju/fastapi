from fastapi import APIRouter, Request, HTTPException
from auth.permission import require_authentication
from database.asyncdb import asyncdb_dependency
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from .models import Notification
from .schemas import NotificationModel, NotificationPatchModel

router = APIRouter(prefix="/notification", tags=["message"])


@router.get("/", response_model=list[NotificationModel])
@require_authentication()
async def get_notification(
    request: Request, db: asyncdb_dependency, limit: int = 10, offset: int = 0
):
    stmt = (
        select(Notification)
        .where(Notification.request_id == request.user.id)
        .order_by(Notification.id.desc())
        .offset(offset)
        .limit(limit)
        .options(joinedload(Notification.user))
    )
    results = (await db.scalars(stmt)).unique().all()

    return results


@router.patch("/markallread")
@require_authentication()
async def mark_all_as_read(request: Request, db: asyncdb_dependency):
    stmt = select(Notification).where(
        Notification.request_id == request.user.id, Notification.read == False
    )
    notifications = (await db.scalars(stmt)).all()

    if not notifications:
        raise HTTPException(status_code=404, detail="notification not found")
    for notification in notifications:
        notification.read = True
    await db.commit()
    return {"msg": "all notification marked as read"}


@router.patch("/{notification_id}")
@require_authentication()
async def mark_as_read_or_change_active_status(
    request: Request,
    db: asyncdb_dependency,
    notification_id: int,
    data: NotificationPatchModel,
):
    stmt = select(Notification).where(
        Notification.request_id == request.user.id,
        Notification.id == notification_id,
    )
    notification = await db.scalar(stmt)
    if not notification:
        raise HTTPException(status_code=404, detail="notification not found")

    if data.read is not None:
        notification.read = data.read
    if data.is_active is not None:
        notification.is_active = data.is_active
    await db.commit()
    return {"msg": "notification updated"}


@router.delete("/delete/{notification_id}")
@require_authentication()
async def delete_notification(
    request: Request, db: asyncdb_dependency, notification_id: int
):
    stmt = select(Notification).where(
        Notification.request_id == request.user.id & Notification.id == notification_id,
    )
    notification = (await db.execute(stmt)).all()
    if not notification:
        raise HTTPException(status_code=404, detail="notification not found")
    await db.delete(notification)
    return {"msg": "notification deleted"}


@router.delete("/deleteall")
@require_authentication()
async def delete_all_notification(request: Request, db: asyncdb_dependency):
    stmt = select(Notification).where(Notification.request_id == request.user.id)
    notifications = (await db.scalars(stmt)).all()
    if not notifications:
        raise HTTPException(status_code=404, detail="notification not found")
    for noti in notifications:
        await db.delete(noti)
    await db.commit()
    return {"msg": "all notification deleted"}
