import structlog

from app.workers.celery_app import app

logger = structlog.get_logger(__name__)


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_export(self, task_id: str, page_id: str, fmt: str = "png") -> dict:
    logger.info("export_started", task_id=task_id, page_id=page_id, format=fmt)
    try:
        # TODO: Load page layout, render SVG, convert to image/PDF
        # Upload result to MinIO
        file_url = f"/exports/{task_id}.{fmt}"
        return {"file_url": file_url, "file_size": 0}
    except Exception as exc:
        logger.error("export_failed", task_id=task_id, error=str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"error": str(exc)}
