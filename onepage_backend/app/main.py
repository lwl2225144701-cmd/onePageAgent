from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.database import engine
from app.core.error_handler import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestIDMiddleware, RequestLoggingMiddleware
from app.core.redis import close_redis, get_redis
from app.models.base import Base


@asynccontextmanager
async def lifespan(ap: FastAPI):
    setup_logging(settings.DEBUG)
    await get_redis()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    ap = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    ap.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    ap.add_middleware(RequestIDMiddleware)
    ap.add_middleware(RequestLoggingMiddleware)

    register_exception_handlers(ap)

    from app.api.v1.router import api_router
    ap.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @ap.get("/health")
    async def health():
        return {"status": "ok"}

    return ap


app = create_app()
