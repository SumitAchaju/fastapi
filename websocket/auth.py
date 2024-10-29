from fastapi import WebSocketException
from jose import JWTError, ExpiredSignatureError, jwt
from starlette import status

from settings import JWT


def verify_token(token: str):
    try:
        payload = jwt.decode(token, JWT["SECRET_KEY"], algorithms=[JWT["ALGORITHM"]])
        user_id = payload.get("id")
        token_type = payload.get("type")
        if user_id is None or str(token_type) == "refresh":
            raise WebSocketException(
                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA, reason="invalid payload"
            )

        return int(user_id)

    except ExpiredSignatureError:
        raise WebSocketException(
            code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA, reason="expired_token"
        )
    except JWTError:
        raise WebSocketException(
            code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA, reason="invalid payload"
        )
