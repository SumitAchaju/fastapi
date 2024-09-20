import contextlib
from typing import Annotated, AsyncIterator
from fastapi import Depends

from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine
from odmantic.session import AIOSession
from settings import DATABASE


class MangoSessionManager:
    def __init__(self, host: str, dbname: str) -> None:
        self.client = AsyncIOMotorClient(host)
        self.engine = AIOEngine(client=self.client, database=dbname)

    async def close(self):
        if self.client is None:
            raise Exception("MangoSessionManager is not initialized")
        await self.client.close()

        self.engine = None
        self.client = None

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AIOSession]:
        if self.engine is None:
            raise Exception("MangoSessionManager is not initialized")

        session = self.engine.session()
        try:
            yield session
        except Exception:
            await session.end()
            raise
        finally:
            await session.end()


mango_sessionmanager = MangoSessionManager(DATABASE["MANGODB_URL"], "chatsystem")


async def get_mango_db():
    if mango_sessionmanager.engine is None:
        raise Exception("MangoSessionManager is not initialized")
    async with mango_sessionmanager.engine.session() as session:
        yield session


mangodb_dependency = Annotated[AIOSession, Depends(get_mango_db)]
