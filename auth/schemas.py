from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class AuthFormData(BaseModel):
    username: str
    password: str


class RefreshToken(BaseModel):
    token: str
