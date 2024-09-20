from fastapi import HTTPException
from starlette import status


class AuthException(HTTPException):
    status_code = status.HTTP_401_UNAUTHORIZED
    details = "Unauthorized Access"

    def __init__(self) -> None:
        super().__init__(self.status_code, self.details)


class TokenExpiredException(AuthException):
    details = "Token has expired"


class InvalidTokenException(AuthException):
    status_code = status.HTTP_400_BAD_REQUEST
    details = "Invalid Token"


class IncorrectCredentialsException(AuthException):
    details = "Incorrect Username or Password"


class AccountBlockedException(AuthException):
    status_code = status.HTTP_403_FORBIDDEN
    details = "Your Account has been Blocked"


class AdminRequiredException(AuthException):
    status_code = status.HTTP_401_UNAUTHORIZED
    details = "required admin access"


class UserNotFoundException(AuthException):
    status_code = status.HTTP_404_NOT_FOUND
    details = "User not found"
