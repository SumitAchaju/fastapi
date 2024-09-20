import typing

from fastapi import HTTPException
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    BaseUser,
)
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from auth.utils import Token, check_account_status
from auth.exceptions import TokenExpiredException


class AuthenticationMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        backend: AuthenticationBackend,
        on_error: typing.Optional[
            typing.Callable[[HTTPConnection, Exception], Response]
        ] = None,
    ) -> None:
        self.app = app
        self.backend = backend
        self.on_error: typing.Callable[[HTTPConnection, Exception], Response] = (
            on_error if on_error is not None else self.default_on_error
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        conn = HTTPConnection(scope)
        try:
            auth_result = await self.backend.authenticate(conn)
        except Exception as exc:
            response = self.on_error(conn, exc)
            await response(scope, receive, send)
            return
        if auth_result is None:
            user = AuthUser(auth=False, token=AuthToken("not_available"))
            auth_result = AuthCredentials(), user
        if auth_result == "token_expired":
            user = AuthUser(auth=False, token=AuthToken("expired"))
            auth_result = AuthCredentials(), user

        scope["auth"], scope["user"] = auth_result
        await self.app(scope, receive, send)

    @staticmethod
    def default_on_error(conn: HTTPConnection, exc: Exception) -> Response:
        return JSONResponse(str(exc), status_code=400)


# Authentication Backend Class
class BearerTokenAuthBackend(AuthenticationBackend):
    """
    This is a custom auth backend class that will allow you to authenticate your request and return auth and user as
    a tuple
    """

    async def authenticate(self, request):
        # This function is inherited from the base class and called by some other class
        if "Authorization" not in request.headers:
            return

        auth = request.headers["Authorization"]
        try:
            scheme, token = auth.split()
            if scheme.lower() != "bearer":
                return
            decoded = Token.verify_token(token)
            if decoded["type"] == "refresh":
                return
        except TokenExpiredException:
            return "token_expired"
        except (ValueError, UnicodeDecodeError, HTTPException):
            return None

        if decoded:
            check_account_status(decoded["status"])
            user = AuthUser(
                auth=True,
                token=AuthToken("verified", token),
                username=decoded["sub"],
                user_id=decoded["id"],
                is_superuser=decoded["is_superuser"],
            )
        else:
            user = AuthUser(auth=False, token=AuthToken("invalid", token))
        return auth, user


class AuthToken:
    token_status_fields = ["expired", "invalid", "verified", "not_available"]

    def __init__(self, tkn_status: str, token: typing.Optional[str] = None):
        self.token = token
        self.status = tkn_status
        if self.status not in self.token_status_fields:
            raise ValueError(f"Token status must be one of {self.token_status_fields}")


class AuthUser(BaseUser):
    def __init__(
        self,
        auth: bool,
        token: AuthToken,
        user_id: int = None,
        username: str = None,
        is_superuser: bool = False,
    ):
        self._auth = auth
        self.token = token
        self.id = user_id
        self.username = username
        self.is_superuser = is_superuser

    @property
    def is_authenticated(self):
        return self._auth
