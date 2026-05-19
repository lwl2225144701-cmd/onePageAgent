import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import OnePageException
from app.schemas.common import ErrorResponse

logger = structlog.get_logger(__name__)


def register_exception_handlers(app):
    @app.exception_handler(OnePageException)
    async def onepage_exception_handler(request: Request, exc: OnePageException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                success=False,
                error_code=exc.error_code,
                message=exc.message,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                success=False,
                error_code="VALIDATION_ERROR",
                message="Request validation failed",
                data={"details": exc.errors()},
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                success=False,
                error_code="INTERNAL_ERROR",
                message=str(exc) if settings.DEBUG else "An unexpected error occurred",
            ).model_dump(),
        )
