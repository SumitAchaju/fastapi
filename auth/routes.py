from fastapi import APIRouter, Request

from query import UserQuery
from database.asyncdb import asyncdb_dependency
from database.mangodb import mangodb_dependency
from .mangomodel import BlackListedRefreshToken, OutstandingRefreshToken
from .schemas import (
    RefreshToken,
    AuthFormData,
)

from .schemas import Token as TokenSchema
from .utils import Token, authenticate_user
from .permission import require_authentication

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token/", response_model=TokenSchema)
async def login_user(
    db: asyncdb_dependency, mangodb: mangodb_dependency, form_data: AuthFormData
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    token = Token(user).get_token()
    await Token.save_refresh_token_to_outstanding(
        mangodb, token.get("refresh_token"), user.id
    )
    return token


@router.post("/token/refresh/", response_model=TokenSchema)
async def refresh_token(
    db: asyncdb_dependency, mangodb: mangodb_dependency, form_data: RefreshToken
):
    ref_token = await Token.verify_refresh_token(mangodb, form_data.token)
    user = await UserQuery.one(db, ref_token["id"])
    new_token = Token(user).get_token()
    await Token.save_refresh_token_to_blacklist(mangodb, form_data.token, user.id)
    await Token.save_refresh_token_to_outstanding(
        mangodb, new_token["refresh_token"], user.id
    )
    return new_token


@router.get("/token/blacklisted/")
@require_authentication(is_superuser=True)
async def blacklisted_token(request: Request, mangodb: mangodb_dependency):
    tokens = await mangodb.find(
        BlackListedRefreshToken, BlackListedRefreshToken.user_id == request.user.id
    )
    return tokens


@router.get("/token/outstanding/")
@require_authentication(is_superuser=True)
async def outstanding_token(request: Request, mangodb: mangodb_dependency):
    tokens = await mangodb.find(
        OutstandingRefreshToken, OutstandingRefreshToken.user_id == request.user.id
    )
    return tokens


@router.get("/token/deleteall/")
@require_authentication(is_superuser=True)
async def delete_tokens(
    request: Request, db: asyncdb_dependency, mongodb: mangodb_dependency
):
    user = await UserQuery.one(db, request.user.id, False)
    data = await Token.delete_all_tokens(mongodb, user.id)
    return data
