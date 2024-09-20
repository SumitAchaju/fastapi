from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from account.models import User


class Query:
    data_model = None

    def __init__(
        self,
        db: AsyncSession,
        filter_data: dict = None,
        options: bool = True,
    ):
        self.db = db
        self.filter_data = filter_data
        self.options = options
        if self.data_model is None:
            raise Exception("data_model is not defined")

    def generate_query(self):
        query = select(self.data_model)
        if self.filter_data:
            for k, v in self.filter_data.items():
                query = query.where(getattr(self.data_model, k) == v)
        if self.options:
            for relation in self.data_model.__mapper__.relationships.items():
                query = query.options(joinedload(getattr(self.data_model, relation[0])))
        return query

    async def get_data(self):
        query = self.generate_query()
        user = (await self.db.scalars(query)).unique()
        return user


class UserQuery(Query):
    data_model = User

    @classmethod
    async def one(cls, db: AsyncSession, user_id: int, option: bool = True) -> User:
        return (await cls(db, {"id": user_id}, option).get_data()).one_or_none()

    @classmethod
    async def one_by_uid(cls, db: AsyncSession, uid: str, option: bool = True) -> User:
        return (await cls(db, {"uid": uid}, option).get_data()).one_or_none()

    @classmethod
    async def all(cls, db: AsyncSession) -> list[User]:
        return (await cls(db, options=False).get_data()).all()
