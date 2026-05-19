import uuid

from fastapi import Request

from app.config import settings


async def get_current_user(request: Request) -> str:
    user_id = request.headers.get(settings.ANONYMOUS_USER_HEADER)
    if user_id:
        return user_id
    return uuid.uuid4().hex
