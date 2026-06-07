import structlog

from app.workers.celery_app import app

logger = structlog.get_logger(__name__)


@app.task(bind=True, max_retries=1)
def run_ai_orchestration(self, task_id: str, user_id: str, input_json: dict) -> dict:
    """Main orchestration task: runs the 6-step AI pipeline and publishes progress via SSE."""
    logger.info(
        "celery_orchestration_received",
        task_id=task_id,
        user_id=user_id,
        celery_task_id=self.request.id,
        retries=self.request.retries,
    )
    print(f"CELERY_TASK_START task_id={task_id} celery_task_id={self.request.id} retries={self.request.retries}", flush=True)

    try:
        from app.ai.orchestrator import AIOrchestrator
        orchestrator = AIOrchestrator()
        result = orchestrator.run_sync(task_id, user_id, input_json)
        logger.info("celery_orchestration_completed", task_id=task_id, celery_task_id=self.request.id)
        print(f"CELERY_TASK_DONE task_id={task_id} celery_task_id={self.request.id}", flush=True)
        return result
    except Exception as exc:
        logger.exception("celery_orchestration_failed", task_id=task_id, celery_task_id=self.request.id, error=str(exc))
        if self.request.retries < self.max_retries:
            logger.warning("celery_orchestration_retrying", task_id=task_id, celery_task_id=self.request.id)
            raise self.retry(exc=exc)
        # Return fallback layout on failure
        from app.ai.fallback.templates import get_fallback_layout
        logger.warning("celery_orchestration_fallback_returned", task_id=task_id, celery_task_id=self.request.id)
        print(f"CELERY_TASK_FALLBACK task_id={task_id} celery_task_id={self.request.id}", flush=True)
        return get_fallback_layout(
            "neutral",
            content_text=input_json.get("text", "") or input_json.get("content_text", ""),
            page_date=input_json.get("page_date", ""),
        )
