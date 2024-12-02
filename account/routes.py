from uuid import uuid4

from PIL import Image
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette import status

import settings
from auth.exceptions import UserNotFoundException, IncorrectCredentialsException
from auth.permission import require_authentication
from auth.utils import Token, bcrypt_context
from database.asyncdb import asyncdb_dependency
from database.mangodb import mangodb_dependency
from message.mangomodel import ChatRoom
from notification.models import Notification, NotificationType, json_data_friend_request
from notification.utils import send_notification_to_user
from query import UserQuery, NotificationQuery
from websocket.manager.connections import room_connections
from .models import User
from .schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    FriendSearch,
    UpdateUsername,
    UpdatePassword,
)
from .utils import (
    create_user,
    update_user_data,
    get_user_for_add,
    create_room,
    change_room_status,
    get_friend_search_res,
    extract_integrity_error,
)

router = APIRouter(prefix="/account", tags=["account"])


@router.post("/createuser", status_code=status.HTTP_201_CREATED)
async def create_new_user(
    request: Request,
    db: asyncdb_dependency,
    mangodb: mangodb_dependency,
    create_user_request: CreateUserRequest,
):
    user = await create_user(db, create_user_request)
    token = Token(user).get_token()
    await Token.save_refresh_token_to_outstanding(
        mangodb, token.get("refresh_token"), user.id
    )
    return token


@router.patch("/updateuser", status_code=status.HTTP_202_ACCEPTED)
@require_authentication()
async def update_user(
    request: Request, db: asyncdb_dependency, update_data: UpdateUserRequest
):
    user = await UserQuery.one(db, request.user.id)
    if user is None:
        raise UserNotFoundException()
    return await update_user_data(db, user, update_data)


@router.post("/upload/profile")
@require_authentication()
async def upload_file(
    request: Request, db: asyncdb_dependency, uploaded_file: UploadFile = File(...)
):
    file_name = str(uuid4()) + "." + uploaded_file.filename
    path = f"{settings.STATIC}/profile/{file_name}"

    with Image.open(uploaded_file.file) as img:
        width, height = img.size
        if width < 300 or height < 300:
            img.save(path)
        else:
            aspect_ratio = width / height

            if aspect_ratio > 1:
                new_height = 300
                new_width = int(new_height * aspect_ratio)
                img.resize((new_width, new_height)).save(path)
            else:
                new_width = 300
                new_height = int(new_width / aspect_ratio)
                img.resize((new_width, new_height)).save(path)

    user = await UserQuery.one(db, request.user.id)
    user.profile = settings.HOSTNAME + "/" + path
    await db.commit()

    return {
        "file": file_name,
        "content": uploaded_file.content_type,
        "path": path,
    }


@router.put("/updateusername")
@require_authentication()
async def update_username(
    request: Request, db: asyncdb_dependency, update_data: UpdateUsername
):
    user = await UserQuery.one(db, request.user.id)
    if user is None:
        raise UserNotFoundException()
    if not bcrypt_context.verify(update_data.password, user.hashed_password):
        raise IncorrectCredentialsException()

    user.username = update_data.username
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=extract_integrity_error(str(exc.orig.__cause__)),
        )

    return user


@router.put("/updatepassword")
@require_authentication()
async def update_password(
    request: Request, db: asyncdb_dependency, update_data: UpdatePassword
):
    user = await UserQuery.one(db, request.user.id)
    if user is None:
        raise UserNotFoundException()
    if not bcrypt_context.verify(update_data.old, user.hashed_password):
        raise IncorrectCredentialsException()
    user.hashed_password = bcrypt_context.hash(update_data.new)
    await db.commit()

    return user


@router.delete("/delete", status_code=status.HTTP_202_ACCEPTED)
@require_authentication()
async def delete_user(
    request: Request,
    db: asyncdb_dependency,
    mangodb: mangodb_dependency,
):

    user = await UserQuery.one(db, request.user.id, False)
    if user is None:
        raise UserNotFoundException()

    # close the room if connected and deactivate the room
    room_query = {"users": {"$elemMatch": {"user_id": user.id}}}
    rooms = await mangodb.find(ChatRoom, room_query)
    for room in rooms:
        if room.is_active:
            room.is_active = False
            await mangodb.commit()
        if str(room.id) in room_connections:
            # close the room
            del room_connections[str(room.id)]

    await db.delete(user)
    await db.commit()
    return user


@router.get("/add/{user_id}")
@require_authentication()
async def add_friend(
    request: Request, db: asyncdb_dependency, mangodb: mangodb_dependency, user_id: int
):
    main_user, second_user, is_already_friend = await get_user_for_add(
        db=db, main_user_id=request.user.id, second_user_id=user_id, operation="friend"
    )

    if is_already_friend:
        raise HTTPException(
            detail="user is already in your friend list", status_code=403
        )

    if second_user in main_user.blocked_user:
        raise HTTPException(
            detail="unblock this user to add to friend list",
            status_code=403,
        )

    if second_user not in main_user.requested_by:
        raise HTTPException(detail="request this user to add friend", status_code=403)

    main_user.requested_by.remove(second_user)
    main_user.friend.append(second_user)

    request_notification = await NotificationQuery(
        db,
        {
            "sender_id": second_user.id,
            "receiver_id": main_user.id,
            "notification_type": NotificationType.FRIEND_REQUEST,
        },
    ).get_by_jsonB_filter({"is_active": True})

    if request_notification is None:
        raise HTTPException("invalid request", status_code=400)

    request_notification.extra_data.update({"is_accepted": True})
    request_notification.extra_data.update({"is_active": False})

    add_friend_notification = Notification(
        sender_id=main_user.id,
        receiver_id=second_user.id,
        notification_type=NotificationType.FRIEND_REQUEST_ACCEPTED,
        message=f"{main_user.first_name} {main_user.last_name} accepted your friend request",
    )
    db.add(add_friend_notification)

    await db.commit()
    await db.refresh(add_friend_notification)

    await send_notification_to_user(add_friend_notification, main_user)

    await create_room(
        mangodb=mangodb,
        main_user_id=main_user.id,
        second_user_id=second_user.id,
        room_type="friend",
    )

    return main_user


@router.get("/request/{user_id}")
@require_authentication()
async def request_user_for_friend(
    request: Request, db: asyncdb_dependency, user_id: int
):
    main_user, second_user, is_already_requested = await get_user_for_add(
        db=db,
        main_user_id=request.user.id,
        second_user_id=user_id,
        operation="requested_user",
    )

    if is_already_requested:
        return main_user

    if second_user in main_user.blocked_user:
        raise HTTPException(
            detail="unblock this user to request this user",
            status_code=403,
        )

    if second_user in main_user.friend:
        raise HTTPException(
            detail="user is already in your friend list",
            status_code=403,
        )

    main_user.requested_user.append(second_user)

    request_notification = Notification(
        sender_id=main_user.id,
        receiver_id=second_user.id,
        notification_type=NotificationType.FRIEND_REQUEST,
        message=f"{main_user.first_name} {main_user.last_name} send you friend request",
        extra_data=json_data_friend_request,
    )

    db.add(request_notification)
    await db.commit()
    await db.refresh(request_notification)

    await send_notification_to_user(request_notification, main_user)

    return main_user


@router.get("/cancel/{user_id}")
@require_authentication()
async def cancel_request(request: Request, db: asyncdb_dependency, user_id: int):
    main_user = await UserQuery.one(db, request.user.id)
    second_user = await UserQuery.one(db, user_id, False)

    if second_user not in main_user.requested_user:
        raise HTTPException(
            detail="user is not in your requested list", status_code=403
        )

    main_user.requested_user.remove(second_user)

    request_notification = await NotificationQuery(
        db,
        {
            "sender_id": main_user.id,
            "receiver_id": second_user.id,
            "notification_type": NotificationType.FRIEND_REQUEST,
        },
    ).get_by_jsonB_filter({"is_active": True}, all=True)

    if request_notification is None:
        raise HTTPException("invalid request", status_code=400)

    for noti in request_notification:
        noti.extra_data.update({"is_canceled": True})
        noti.extra_data.update({"is_active": False})

    cancel_notification = Notification(
        sender_id=main_user.id,
        receiver_id=second_user.id,
        notification_type=NotificationType.FRIEND_REQUEST_CANCELED,
        message=f"{main_user.first_name} {main_user.last_name} canceled friend request",
        linked_notification_id=(
            request_notification[0].id if request_notification else None
        ),
    )

    db.add(cancel_notification)
    await db.commit()
    await db.refresh(cancel_notification)

    await send_notification_to_user(cancel_notification, main_user)

    return main_user


@router.get("/unfriend/{user_id}")
@require_authentication()
async def unfriend_user(
    request: Request, db: asyncdb_dependency, mangodb: mangodb_dependency, user_id: int
):
    main_user, second_user, is_not_friend = await get_user_for_add(
        db, main_user_id=request.user.id, second_user_id=user_id, operation="unfriend"
    )

    if is_not_friend:
        raise HTTPException(detail="user is not in your friend list", status_code=403)

    if second_user in main_user.friend:
        main_user.friend.remove(second_user)
    elif second_user in main_user.friend_by:
        main_user.friend_by.remove(second_user)
    else:
        return main_user

    unfriend_notificaiton = Notification(
        sender_id=main_user.id,
        receiver_id=second_user.id,
        notification_type=NotificationType.UNFRIEND,
        message=f"{main_user.first_name} {main_user.last_name} unfriend you",
    )
    db.add(unfriend_notificaiton)
    await db.commit()
    await db.refresh(unfriend_notificaiton)
    await send_notification_to_user(unfriend_notificaiton, main_user)

    # close the room if connected and deactivate the room
    room = await change_room_status(main_user.id, second_user.id, mangodb, False)
    if room:
        if str(room.id) in room_connections:
            await room_connections[str(room.id)].close_room()

    return main_user


@router.get("/block/{user_id}")
@require_authentication()
async def block_user(
    request: Request, db: asyncdb_dependency, mangodb: mangodb_dependency, user_id: int
):
    main_user, second_user, is_already_blocked = await get_user_for_add(
        db,
        main_user_id=request.user.id,
        second_user_id=user_id,
        operation="blocked_user",
    )

    if is_already_blocked:
        return main_user

    main_user.blocked_user.append(second_user)

    block_notification = Notification(
        sender_id=main_user.id,
        receiver_id=second_user.id,
        notification_type=NotificationType.BLOCK_FRIEND,
        message=f"{main_user.first_name} {main_user.last_name} blocked you",
    )
    db.add(block_notification)

    await db.commit()
    await db.refresh(block_notification)

    await send_notification_to_user(block_notification, main_user)

    # close the room if connected and deactivate the room
    room = await change_room_status(main_user.id, second_user.id, mangodb, False)
    if room:
        if str(room.id) in room_connections:
            print("closed room: ", room.id)
            await room_connections[str(room.id)].close_room()

    return main_user


@router.get("/unblock/{user_id}")
@require_authentication()
async def unblock_user(
    request: Request, db: asyncdb_dependency, mangodb: mangodb_dependency, user_id: int
):
    main_user = await UserQuery.one(db, request.user.id)
    second_user = await UserQuery.one(db, user_id, False)

    if second_user not in main_user.blocked_user:
        raise HTTPException(detail="user is not in your blocked list", status_code=403)

    main_user.blocked_user.remove(second_user)
    unblock_notification = Notification(
        sender_id=main_user.id,
        receiver_id=second_user.id,
        notification_type=NotificationType.UNBLOCK_FRIEND,
        message=f"{main_user.first_name} {main_user.last_name} unblocked you",
    )
    db.add(unblock_notification)
    await db.commit()
    await db.refresh(unblock_notification)

    await send_notification_to_user(unblock_notification, main_user)

    if second_user in main_user.friend or second_user in main_user.friend_by:
        if second_user not in main_user.blocked_by:
            await change_room_status(main_user.id, second_user.id, mangodb, True)

    return main_user


@router.get("/search", response_model=list[FriendSearch])
@require_authentication()
async def search_user(
    request: Request,
    db: asyncdb_dependency,
    search_type: str = "",
    search: str = "",
    offset: int = 0,
    limit: int = 10,
):
    if search_type not in ("name", "uid", "contact"):
        raise HTTPException(
            detail="search type must be in (name, uid, contact)",
            status_code=400,
        )

    self_user = await UserQuery.one(db, request.user.id)

    if search == "" or search_type == "":
        stmt = (
            select(User).where(User.id != request.user.id).offset(offset).limit(limit)
        )
        users = (await db.scalars(stmt)).unique().all()

        return get_friend_search_res(users, self_user)

    stmt = select(User)

    if search_type == "name":
        if search.split(" ").__len__() == 1:
            stmt = stmt.where(
                User.first_name.ilike(f"%{search}%")
                | User.last_name.ilike(f"%{search}")
            )
        else:
            stmt = stmt.where(
                (
                    User.first_name.ilike(f"%{search.split(" ")[0]}%")
                    & User.last_name.ilike(f"%{search.split(" ")[1]}%")
                )
                | (
                    User.first_name.ilike(f"%{search.split(" ")[1]}%")
                    & User.last_name.ilike(f"%{search.split(" ")[0]}%")
                )
            )

    elif search_type == "uid":
        stmt = stmt.where(User.uid == search)
    else:
        try:
            stmt = stmt.where(User.contact_number == int(search))
        except ValueError:
            raise HTTPException(
                detail="search word is not valid for contact number", status_code=400
            )

    stmt = stmt.offset(offset).limit(limit)

    users = (await db.scalars(stmt)).unique().all()

    return get_friend_search_res(users, self_user)
