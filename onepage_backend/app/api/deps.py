from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db as _get_db
from app.core.redis import get_redis as _get_redis
from app.core.security import get_current_user as _get_current_user


async def get_db():
    async for session in _get_db():
        yield session


async def get_redis():
    return await _get_redis()


async def get_current_user(request: Request) -> str:
    return await _get_current_user(request)
