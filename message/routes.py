from fastapi import APIRouter, Request, HTTPException
from websocket.manager import main_connections
from database.asyncdb import asyncdb_dependency
from query import UserQuery
from auth.permission import require_authentication
from database.mangodb import mangodb_dependency
from .mangomodel import ChatRoom, Message
from sqlalchemy import select
from account.models import User
from .schema import ChatHistoryResponse, OnlineUserResponse
from account.schemas import UserModel
from bson import ObjectId
from bson.errors import InvalidId
from .mangomodel import datetime_format
from datetime import datetime


router = APIRouter(prefix="/message", tags=["message"])


@router.get("/room")
@require_authentication()
async def get_rooms(request: Request, mangodb: mangodb_dependency):
    rooms = await mangodb.find(ChatRoom)

    return rooms


@router.get("/onlineuser", response_model=list[OnlineUserResponse])
@require_authentication()
async def get_online_user(
    request: Request, db: asyncdb_dependency, mangodb: mangodb_dependency
):
    user = await UserQuery.one(db, request.user.id, True)
    online_users = []
    for friend in (*user.friend, *user.friend_by):
        if friend.id in main_connections.keys():
            online_users.append(friend)
    response = []
    for user in online_users:
        room_users = [user.id, request.user.id]
        query = {"users.user_id": {"$all": room_users}}
        room = await mangodb.find_one(ChatRoom, query)
        response.append(OnlineUserResponse(user=UserModel(**user.__dict__), room=room))

    return response


@router.get("/history", response_model=list[ChatHistoryResponse])
@require_authentication()
async def get_chat_history(
    request: Request, db: asyncdb_dependency, mangodb: mangodb_dependency
):
    rooms = await mangodb.find(ChatRoom, {"users.user_id": request.user.id})
    history_user_id = []
    history_user_room = []
    for room in rooms:
        room_data = {"room": room, "users": []}
        for usr in room.users:
            if usr.user_id != request.user.id:
                history_user_id.append(usr.user_id)
                room_data["users"].append(usr.user_id)
        history_user_room.append(room_data)

    history_user_query = select(User).filter(User.id.in_(history_user_id))
    history_user = (await db.scalars(history_user_query)).unique().all()

    results = []

    for room in history_user_room:
        messages = await mangodb.find(
            Message,
            Message.room_id == str(room["room"].id),
            limit=5,
            sort=Message.id.desc(),
        )
        unseen_msg_quantity = 0
        for msg in messages:
            if msg.status != "seen" and msg.sender_id != request.user.id:
                unseen_msg_quantity += 1

        msg = messages[0] if messages else None

        result = ChatHistoryResponse(
            room=room["room"],
            users=[],
            message=msg,
            quantity=unseen_msg_quantity,
        )
        for room_usr in room["users"]:
            for usr in history_user:
                if usr.id == room_usr:
                    result.users.append(UserModel(**usr.__dict__))
                    break
        results.append(result)

    sorted_results = sorted(
        results,
        key=lambda chatobj: (
            datetime.strptime(chatobj.message.created_at, datetime_format)
            if chatobj.message != None
            else datetime.strptime(chatobj.room.created_at, datetime_format)
        ),
        reverse=True,
    )

    return sorted_results


@router.get("/room/{room_id}")
@require_authentication()
async def get_rooms(request: Request, mangodb: mangodb_dependency, room_id: str):
    try:
        room = await mangodb.find_one(ChatRoom, ChatRoom.id == ObjectId(room_id))
        return room
    except InvalidId:
        raise HTTPException(detail="invalid id", status_code=400)


@router.get("/msg/{room_id}")
@require_authentication()
async def get_room_messages(
    request: Request, mangodb: mangodb_dependency, room_id: str, offset: int, limit: int
):
    try:
        room = await mangodb.find_one(ChatRoom, ChatRoom.id == ObjectId(room_id))
        if not room:
            raise InvalidId

        if request.user.id not in [usr.user_id for usr in room.users]:
            raise HTTPException(detail="user not in room", status_code=403)

    except InvalidId:
        raise HTTPException(detail="invalid room id", status_code=403)

    messages = await mangodb.find(
        Message,
        Message.room_id == room_id,
        limit=limit,
        skip=offset,
        sort=Message.id.desc(),
    )
    messages.reverse()
    return messages


@router.get("/friend/{room_id}")
@require_authentication()
async def get_room_friend(
    request: Request, mangodb: mangodb_dependency, db: asyncdb_dependency, room_id: str
):
    try:
        room_object_id = ObjectId(room_id)
    except InvalidId:
        raise HTTPException(detail="invalid room id", status_code=403)

    room = await mangodb.find_one(ChatRoom, ChatRoom.id == room_object_id)
    if request.user.id not in [usr.user_id for usr in room.users]:
        raise HTTPException(detail="user not in room", status_code=403)
    friend_user_id = [
        usr.user_id for usr in room.users if usr.user_id != request.user.id
    ]

    friend_users_query = select(User).filter(User.id.in_(friend_user_id))
    friend_users = (await db.scalars(friend_users_query)).unique().all()
    if friend_users:
        if room.type == "friend":
            return friend_users[0]
    return friend_users
