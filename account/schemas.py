from typing import Annotated

from pydantic import (
    BaseModel,
    EmailStr,
    field_validator,
    Field,
    StringConstraints,
    HttpUrl,
)

stringType = Annotated[
    str, StringConstraints(min_length=2, max_length=50, strip_whitespace=True)
]

usernameType = Annotated[
    str, StringConstraints(min_length=4, max_length=50, strip_whitespace=True)
]

passwordType = Annotated[
    str, StringConstraints(min_length=8, max_length=50, strip_whitespace=True)
]


class CreateUserRequest(BaseModel):
    first_name: stringType
    last_name: stringType
    email: EmailStr
    address: stringType
    contact_number_country_code: int = Field(..., ge=0)
    contact_number: int
    superuser_pass: str | None = None
    username: usernameType
    password: passwordType

    # noinspection PyNestedDecorators
    @field_validator("contact_number")
    @classmethod
    def must_contain_ten_numbers(cls, v: int) -> int:
        if len(str(v)) != 10:
            raise ValueError("Contact number must be 10 digits")
        return v

    # noinspection PyNestedDecorators
    @field_validator("first_name", "last_name")
    @classmethod
    def must_not_contain_num_in_name(cls, v: str, info) -> str:
        contains_num = any(ch.isdigit() for ch in v)
        if contains_num:
            raise ValueError(f"{info.field_name} must not contain numbers")
        return v


class UpdateUserRequest(BaseModel):
    first_name: stringType | None = None
    last_name: stringType | None = None
    address: stringType | None = None
    username: usernameType | None = None
    password: passwordType | None = None

    # noinspection PyNestedDecorators
    @field_validator("first_name", "last_name")
    @classmethod
    def must_not_contain_num_in_name(cls, v: str, info) -> str:
        contains_num = any(ch.isdigit() for ch in v)
        if contains_num:
            raise ValueError(f"{info.field_name} must not contain numbers")
        return v


class UserModel(BaseModel):
    id: int
    uid: str
    username: usernameType
    profile: HttpUrl
    email: EmailStr
    first_name: stringType
    last_name: stringType
    contact_number_country_code: int = Field(..., ge=0)
    contact_number: int
    address: stringType

    # noinspection PyNestedDecorators
    @field_validator("contact_number")
    @classmethod
    def must_contain_ten_numbers(cls, v: int) -> int:
        if len(str(v)) != 10:
            raise ValueError("Contact number must be 10 digits")
        return v


class UserResponse(UserModel):
    blocked_user: list["UserModel"] | None = None
    blocked_by: list["UserModel"] | None = None

    friend: list["UserModel"] | None = None
    friend_by: list["UserModel"] | None = None

    requested_user: list["UserModel"] | None = None
    requested_by: list["UserModel"] | None = None


friend_search_status = ("friend", "requested", "blocked", "requested_by", "none")


class FriendSearch(UserModel):
    friend_status: str = "none"

    @field_validator("friend_status")
    @classmethod
    def must_be_valid_status(cls, v: str) -> str:
        if v not in friend_search_status:
            raise ValueError(f"Status must be in {friend_search_status}")
        return v


class UpdateUsername(BaseModel):
    username: usernameType
    password: passwordType


class UpdatePassword(BaseModel):
    old: str
    new: passwordType
