from datetime import datetime, timezone

from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError, ExpiredSignatureError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from account.models import User
from query import UserQuery
from .exceptions import (
    TokenExpiredException,
    AccountBlockedException,
    AuthException,
    InvalidTokenException,
    IncorrectCredentialsException,
)
from .mangomodel import (
    OutstandingRefreshToken,
    BlackListedRefreshToken,
)
from settings import JWT
from odmantic.session import AIOSession

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="/auth/token")


def check_account_status(acc_status: str):
    if acc_status == "blocked":
        raise AccountBlockedException()


async def authenticate_user(db: AsyncSession, username: str, password: str):
    user = (await UserQuery(db, {"username": username}).get_data()).one_or_none()
    if not user or not bcrypt_context.verify(password, user.hashed_password):
        raise IncorrectCredentialsException()
    return user


class Token:
    # must be field name of User model
    extra_encode_fields = [
        "is_superuser",
        "status",
    ]

    def __init__(self, user: User):

        self.user = user
        self.refresh_token = None
        self.access_token = None

    def get_token(self):
        return {
            "access_token": self.create_token("access"),
            "refresh_token": self.create_token("refresh"),
            "token_type": "bearer",
        }

    def get_encode_data(self, token_type: str):
        encode = {
            "sub": self.user.username,
            "id": self.user.id,
            "type": token_type,
            "exp": (
                datetime.now(tz=timezone.utc)
                + (
                    JWT["ACCESS_TOKEN_EXPIRES"]
                    if token_type == "access"
                    else JWT["REFRESH_TOKEN_EXPIRES"]
                )
            ),
        }
        for field in self.extra_encode_fields:
            encode[field] = getattr(self.user, field)
        return encode

    def create_token(self, token_type: str):
        encode = self.get_encode_data(token_type)
        token = jwt.encode(encode, JWT["SECRET_KEY"], algorithm=JWT["ALGORITHM"])
        if token_type == "access":
            self.access_token = token
        else:
            self.refresh_token = token
        return token

    @staticmethod
    def verify_token(token: str):
        try:
            payload = jwt.decode(
                token, JWT["SECRET_KEY"], algorithms=[JWT["ALGORITHM"]]
            )
            return payload

        except ExpiredSignatureError:
            raise TokenExpiredException()
        except JWTError:
            raise AuthException()

    @staticmethod
    async def verify_refresh_token(mangodb: AIOSession, token: str):
        refresh_token = Token.verify_token(token)
        if refresh_token["type"] == "access":
            raise InvalidTokenException()

        outstanding_token = await mangodb.find_one(
            OutstandingRefreshToken, OutstandingRefreshToken.token == token
        )
        if outstanding_token is None:
            raise InvalidTokenException()

        blacklisted_token = await mangodb.find_one(
            BlackListedRefreshToken, BlackListedRefreshToken.token == token
        )
        if blacklisted_token:
            raise InvalidTokenException()

        return refresh_token

    @staticmethod
    async def save_refresh_token_to_outstanding(
        mangodb: AIOSession, token: str, user_id: int
    ):
        refresh_token = OutstandingRefreshToken(user_id=user_id, token=token)
        await mangodb.save(refresh_token)

    @staticmethod
    async def save_refresh_token_to_blacklist(
        mangodb: AIOSession, token: str, user_id: int
    ):
        outstanding = await mangodb.find_one(
            OutstandingRefreshToken,
            (OutstandingRefreshToken.user_id == user_id) & (OutstandingRefreshToken.token == token)
        )
        if outstanding:
            await mangodb.delete(outstanding)
        else:
            raise InvalidTokenException()

        refresh_token = BlackListedRefreshToken(
            token=token, user_id=user_id, expires_at=outstanding.expires_at
        )
        await mangodb.save(refresh_token)

    @staticmethod
    async def delete_all_tokens(mangodb: AIOSession, user_id: int):
        outstanding_tokens = await mangodb.find(
            OutstandingRefreshToken, OutstandingRefreshToken.user_id == user_id
        )
        for t in outstanding_tokens:
            await mangodb.delete(t)

        blacklisted_tokens = await mangodb.find(
            BlackListedRefreshToken, BlackListedRefreshToken.user_id == user_id
        )
        for t in blacklisted_tokens:
            await mangodb.delete(t)

        return {
            "user_id": user_id,
            "deleted_outstanding_tokens": outstanding_tokens,
            "deleted_black_token": blacklisted_tokens,
        }
