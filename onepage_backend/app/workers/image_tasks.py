import structlog

from app.workers.celery_app import app

logger = structlog.get_logger(__name__)


@app.task(bind=True, max_retries=1)
def run_image_understanding(self, task_id: str, image_urls: list[str]) -> dict:
    logger.info("image_understanding_started", task_id=task_id, count=len(image_urls))
    try:
        # TODO: Call Qwen-VL client when API keys configured
        images = [
            {
                "url": url,
                "description": "",
                "tags": [],
                "dominant_colors": [],
            }
            for url in image_urls
        ]
        return {"images": images}
    except Exception as exc:
        logger.error("image_understanding_failed", task_id=task_id, error=str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"images": [], "error": str(exc)}
