import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import auth.routes as authroutes
import settings
import websocket.routes as wsroutes
from query import UserQuery
from auth.middleware import BearerTokenAuthBackend, AuthenticationMiddleware
from auth.permission import require_authentication
from database.asyncdb import asyncdb_dependency, sessionmanager
from database.mangodb import mangodb_dependency, mango_sessionmanager
import account.routes as accountRoutes
import message.routes as messageRoutes
import notification.routes as notificationRoutes
import json

logging.basicConfig(
    stream=sys.stdout, level=logging.DEBUG if settings.DEBUG else logging.INFO
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    # on startup code

    yield

    # on shutdown code
    if sessionmanager.get_engine() is not None:
        # Close the DB connection
        await sessionmanager.close()

    if mango_sessionmanager.client is not None:
        mango_sessionmanager.client.close()


app = FastAPI(lifespan=lifespan)

app.mount("/files", StaticFiles(directory="files"), "files")


@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(json.loads(exc.json()), status_code=422)


app.include_router(authroutes.router)
app.include_router(accountRoutes.router)
app.include_router(messageRoutes.router)
app.include_router(notificationRoutes.router)
app.include_router(wsroutes.router)

origins = ["http://localhost:5173", "http://127.0.0.1:8000"]
# noinspection PyTypeChecker
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# noinspection PyTypeChecker
app.add_middleware(
    AuthenticationMiddleware,
    backend=BearerTokenAuthBackend(),
)


@app.get("/")
async def root(request: Request, mangodb: mangodb_dependency):
    return {"msg": "hello sumit"}


@app.get("/users")
@require_authentication()
async def read_users(request: Request, db: asyncdb_dependency):
    results = await UserQuery.all(db)
    return results


@app.get("/getuser/")
@require_authentication()
async def get_user(
    request: Request,
    db: asyncdb_dependency,
    uid: str | None = None,
    user_id: int | None = None,
):
    if user_id:
        user = await UserQuery.one(db, user_id)
        return user
    if uid:
        user = await UserQuery.one_by_uid(db, uid)
        return user
    return await UserQuery.one(db, request.user.id)