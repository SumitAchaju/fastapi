from sqlalchemy import ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, Relationship
from shortuuid import uuid

from database.base import Base


class BlockedUser(Base):
    __tablename__ = "BlockedUser"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    blocked_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )


class RequestedUser(Base):
    __tablename__ = "RequestedUser"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    requested_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )


class Friend(Base):
    __tablename__ = "Friend"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    friend_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    uid: Mapped[str] = mapped_column(server_default=uuid())
    first_name: Mapped[str]
    last_name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    address: Mapped[str] = mapped_column(nullable=False, server_default="")
    profile: Mapped[str] = mapped_column(nullable=False, server_default="")
    contact_number_country_code: Mapped[int] = mapped_column(
        nullable=False, server_default="977"
    )
    contact_number: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True, server_default="0"
    )
    is_superuser: Mapped[bool] = mapped_column(server_default="False")
    status: Mapped[str] = mapped_column(server_default="active")
    username: Mapped[str] = mapped_column(unique=True)
    hashed_password: Mapped[str]

    blocked_user: Mapped[list["User"]] = Relationship(
        secondary=BlockedUser.__tablename__,
        primaryjoin="BlockedUser.user_id == User.id",
        secondaryjoin="BlockedUser.blocked_user_id == User.id",
        lazy="joined",
        backref="blocked_by",
    )

    friend: Mapped[list["User"]] = Relationship(
        secondary=Friend.__tablename__,
        primaryjoin="Friend.user_id == User.id",
        secondaryjoin="Friend.friend_user_id == User.id",
        lazy="joined",
        backref="friend_by",
    )

    requested_user: Mapped[list["User"]] = Relationship(
        secondary=RequestedUser.__tablename__,
        primaryjoin="RequestedUser.user_id == User.id",
        secondaryjoin="RequestedUser.requested_user_id == User.id",
        lazy="joined",
        backref="requested_by",
    )
