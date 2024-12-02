import contextlib
from typing import Any, AsyncIterator, Annotated

import ujson
from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)

from settings import DATABASE


class DatabaseSessionManager:
    def __init__(self, host: str, engine_kwargs: dict[str, Any] = {}):
        self._engine = create_async_engine(host, **engine_kwargs)
        self._sessionmaker = async_sessionmaker(
            autocommit=False, bind=self._engine, expire_on_commit=False
        )

    def get_engine(self) -> AsyncEngine:
        if self._engine is None:
            raise Exception("engine hasnot been initialized")
        return self._engine

    async def close(self):
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")
        await self._engine.dispose()

        self._engine = None
        self._sessionmaker = None

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        async with self._engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def ujson_serializer(obj):
    return ujson.dumps(obj)


def ujson_deserializer(obj):
    return ujson.loads(obj)


sessionmanager = DatabaseSessionManager(
    DATABASE.get("URL"),
    {
        "json_serializer": ujson_serializer,
        "json_deserializer": ujson_deserializer,
    },
)


async def get_db_session():
    # noinspection PyArgumentList
    async with sessionmanager.session() as session:
        yield session


asyncdb_dependency = Annotated[AsyncSession, Depends(get_db_session)]
