import structlog
import logging

from app.config import settings


def setup_logging(debug: bool = False):
    configured_level = str(settings.PIPELINE_LOG_LEVEL or "").upper()
    level = configured_level if configured_level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else ("DEBUG" if debug else "INFO")
    logging.basicConfig(
        level=level,
        format="%(message)s",
        force=True,
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    external_level = getattr(logging, str(settings.LOG_EXTERNAL_LIBRARIES or "WARNING").upper(), logging.WARNING)
    for logger_name in [
        "httpcore",
        "httpx",
        "PIL",
        "PIL.PngImagePlugin",
        "PIL.JpegImagePlugin",
        "asyncio",
        "openai",
        "mcp",
        "mcp.client",
        "mcp.server",
    ]:
        logging.getLogger(logger_name).setLevel(external_level)
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
