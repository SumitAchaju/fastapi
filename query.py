from typing import Coroutine, cast, Sequence, Type, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from account.models import User
from notification.models import Notification
from abc import ABC, abstractmethod

T = TypeVar("T")


class Query(Generic[T], ABC):
    def __init__(
        self,
        db: AsyncSession,
        filter_data: dict | None = None,
        options: bool = True,
        limit: int | None = None,
        offset: int | None = None,
        order_by: tuple[str, str] | None = None,
    ):
        if filter_data:
            self.validate_model_attribute(tuple(filter_data.keys()), self.data_model)
        if order_by:
            if order_by[1] not in ("asc", "desc"):
                raise ValueError("order_by[1] must be 'asc' or 'desc'")
            self.validate_model_attribute((order_by[0],), self.data_model)
        self.db = db
        self.filter_data = filter_data
        self.options = options
        self.limit = limit
        self.offset = offset
        self.order_by = order_by

    @staticmethod
    def validate_model_attribute(data: tuple[str, ...], model: T):
        if not all([hasattr(model, k) for k in data]):
            raise AttributeError(f"{data} is not a valid attribute of {model.__name__}")

    @property
    @abstractmethod
    def data_model(self) -> T:
        """Return the data model to be queried"""
        pass

    def generate_query(self):
        query = select(self.data_model)
        if self.filter_data:
            for k, v in self.filter_data.items():
                if hasattr(self.data_model, k):
                    query = query.where(
                        cast("ColumnElement[bool]", getattr(self.data_model, k) == v)
                    )
                else:
                    raise AttributeError(
                        f"{k} is not a valid attribute of {self.data_model.__name__}"
                    )
        if self.options:
            for relation in self.data_model.__mapper__.relationships.items():
                query = query.options(joinedload(getattr(self.data_model, relation[0])))
        if self.order_by:
            query = query.order_by(
                getattr(self.data_model, self.order_by[0]).asc()
                if self.order_by[1] == "asc"
                else getattr(self.data_model, self.order_by[0]).desc()
            )
        if self.offset:
            query = query.offset(self.offset)
        if self.limit:
            query = query.limit(self.limit)

        return query

    async def get_data(self):
        query = self.generate_query()
        data = (await self.db.scalars(query)).unique()
        return data

    @classmethod
    async def one(
        cls, db: AsyncSession, model_id: int, option: bool = True
    ) -> T | None:
        return (await cls(db, {"id": model_id}, option).get_data()).one_or_none()

    @classmethod
    async def all(cls, db: AsyncSession) -> Sequence[T]:
        return (await cls(db, options=False).get_data()).all()

    async def get_all_filter(self) -> Sequence[T]:
        return (await self.get_data()).all()

    async def get_one_filter(self) -> T | None:
        return (await self.get_data()).one_or_none()


class UserQuery(Query[Type[User]]):
    data_model = User

    @classmethod
    async def one_by_uid(cls, db: AsyncSession, uid: str, option: bool = True) -> User:
        return (await cls(db, {"uid": uid}, option).get_data()).one_or_none()


class NotificationQuery(Query[Type[Notification]]):
    data_model = Notification

    @classmethod
    def get_all_by_reciever_id(
        cls,
        db: AsyncSession,
        reciever_id: int,
        option: bool = True,
        limit: int | None = None,
        offset: int | None = None,
        order_by: tuple[str, str] | None = None,
    ) -> Coroutine[any, any, Sequence[type[Notification]]]:
        return cls(
            db, {"receiver_id": reciever_id}, option, limit, offset, order_by
        ).get_all_filter()

    async def get_by_jsonB_filter(self, jsonB_filter: dict, all: bool = False):
        query = self.generate_query()
        query = query.where(
            cast(
                "ColumnElement[bool]",
                getattr(self.data_model, "extra_data").contains(jsonB_filter),
            )
        )

        data = (await self.db.scalars(query)).unique()
        if all:
            return data.all()
        return data.one_or_none()
