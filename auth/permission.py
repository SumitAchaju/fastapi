import functools

from auth.exceptions import TokenExpiredException, AuthException, AdminRequiredException


def require_authentication(is_superuser: bool = False):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper_fun(*args, **kwargs):
            request = kwargs.get("request")
            if not request:
                raise Exception(
                    "requires request parameter in routes for authentication"
                )
            if request.user.token.status == "expired":
                raise TokenExpiredException()

            if not request.user.is_authenticated:
                raise AuthException()

            if is_superuser and not request.user.is_superuser:
                raise AdminRequiredException()

            return await func(*args, **kwargs)

        return wrapper_fun

    return decorator
