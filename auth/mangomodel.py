from odmantic import Model, Field
from datetime import datetime
from settings import JWT


class OutstandingRefreshToken(Model):
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now() + JWT["REFRESH_TOKEN_EXPIRES"]
    )
    token: str
    user_id: int


class BlackListedRefreshToken(Model):
    blacklisted_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime
    token: str
    user_id: int
