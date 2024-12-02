from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from account.models import User
from account.schemas import CreateUserRequest, UpdateUserRequest
from auth.utils import bcrypt_context
from settings import SUPER_USER, HOSTNAME, STATIC
from query import UserQuery
from odmantic.session import AIOSession
from message.mangomodel import ChatRoom, RoomUser
from .schemas import FriendSearch

integrity_error_fields = ["email", "username", "contact_number"]


def extract_integrity_error(detail: str) -> str:
    for field in integrity_error_fields:
        if detail.__contains__(f"Key ({field})"):
            return f"user with {field} already exists!!"

    return "something went wrong in database"


async def create_user(db: AsyncSession, user_data: CreateUserRequest):
    user = user_data.model_dump()

    superuser_pass = user.pop("superuser_pass")
    password = user.pop("password")

    user["profile"] = f"{HOSTNAME}/{STATIC}/profile/default_profile.jpg"

    if superuser_pass and superuser_pass == SUPER_USER["ACCESS_PASSWORD"]:
        is_superuser = True
    else:
        is_superuser = False
    user_model = User(**user)

    user_model.is_superuser = is_superuser
    user_model.hashed_password = bcrypt_context.hash(password)
    db.add(user_model)

    try:
        await db.commit()
        await db.refresh(user_model)

    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=extract_integrity_error(str(exc.orig.__cause__)),
        )

    return user_model


async def update_user_data(
    db: AsyncSession, user: User, update_data: UpdateUserRequest
):
    user_data = update_data.model_dump()

    for key, value in user_data.items():
        if value is not None and key != "password":
            setattr(user, key, value)
        elif value is not None and key == "password":
            user.hashed_password = bcrypt_context.hash(value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=extract_integrity_error(str(exc.orig.__cause__)),
        )

    return user


async def get_user_for_add(
    db: AsyncSession, main_user_id: int, second_user_id: int, operation: str
) -> tuple[User, User, bool]:
    main_user = await UserQuery.one(db, main_user_id)
    second_user = await UserQuery.one(db, second_user_id, False)
    is_already_in_operation = False

    if main_user is None or second_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if operation == "unfriend":
        if (
            second_user not in main_user.friend
            and second_user not in main_user.friend_by
        ):
            is_already_in_operation = True

    elif operation == "friend":
        if second_user in main_user.friend or second_user in main_user.friend_by:
            is_already_in_operation = True

    elif second_user in getattr(main_user, operation):
        is_already_in_operation = True

    return main_user, second_user, is_already_in_operation


async def create_room(
    mangodb: AIOSession, main_user_id: int, second_user_id: int, room_type: str
) -> ChatRoom:
    room_users = [main_user_id, second_user_id]
    query = {"users.user_id": {"$all": room_users}}
    room = await mangodb.find_one(ChatRoom, query)

    if not room:
        new_room = ChatRoom(
            users=[
                RoomUser(user_id=main_user_id, isAdmin=True),
                RoomUser(user_id=second_user_id, isAdmin=True),
            ],
            type=room_type,
            is_active=True,
        )

        await mangodb.save(new_room)

        return new_room

    room.is_active = True

    await mangodb.save(room)

    return room


async def change_room_status(
    main_user, second_user, mangodb: AIOSession, status: bool
) -> ChatRoom | None:
    room_users = [main_user, second_user]
    query = {"users.user_id": {"$all": room_users}}
    room = await mangodb.find_one(ChatRoom, query)
    if room:
        if room.is_active != status:
            room.is_active = status
            await mangodb.save(room)

    return room


def get_friend_search_res(users: list[User], self_user: User):
    response = []
    for usr in users:
        if usr in self_user.friend or usr in self_user.friend_by:
            status = "friend"
        elif usr in self_user.requested_user:
            status = "requested"
        elif usr in self_user.requested_by:
            status = "requested_by"
        elif usr in self_user.blocked_user:
            status = "blocked"
        else:
            status = "none"

        response.append(
            FriendSearch(
                **usr.__dict__,
                friend_status=status,
            )
        )
    return response
