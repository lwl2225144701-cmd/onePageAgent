import structlog
from celery.signals import task_prerun, task_postrun, task_failure, worker_process_init, worker_shutdown

from app.config import settings
from app.core.logging import setup_logging

logger = structlog.get_logger(__name__)


@task_prerun.connect
def on_task_start(sender, task_id, args, kwargs, **extra):
    logger.info("task_started", task_name=sender.name, task_id=task_id)


@task_postrun.connect
def on_task_success(sender, task_id, retval, state, **extra):
    logger.info("task_completed", task_name=sender.name, task_id=task_id)


@task_failure.connect
def on_task_failure(sender, task_id, exception, traceback, **extra):
    logger.error("task_failed", task_name=sender.name, task_id=task_id, error=str(exception))


@worker_process_init.connect
def on_worker_process_init(**_extra):
    setup_logging(settings.DEBUG)
    logger.info("worker_process_init", build_commit=settings.BUILD_COMMIT_SHA, layout_engine=settings.LAYOUT_ENGINE_VERSION)
    print(
        f"ONEPAGE_WORKER_BUILD_VERSION build_commit={settings.BUILD_COMMIT_SHA} layout_engine={settings.LAYOUT_ENGINE_VERSION}",
        flush=True,
    )
    try:
        from app.core.database import engine

        engine.sync_engine.dispose(close=False)
        logger.info("worker_db_engine_disposed")
    except Exception as exc:
        logger.warning("worker_db_engine_dispose_failed", error=str(exc))


@worker_shutdown.connect
def on_worker_shutdown(**_extra):
    logger.info("worker_shutdown")
