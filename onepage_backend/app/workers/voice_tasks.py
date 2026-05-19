import structlog

from app.workers.celery_app import app

logger = structlog.get_logger(__name__)


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_speech_recognition(self, task_id: str, audio_url: str) -> dict:
    logger.info("speech_recognition_started", task_id=task_id)
    try:
        # TODO: Call SenseVoiceSmall client when API keys configured
        result = {
            "text": "",
            "emotion": "neutral",
            "emotion_confidence": 0.5,
        }
        return result
    except Exception as exc:
        logger.error("speech_recognition_failed", task_id=task_id, error=str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"text": "", "emotion": "neutral", "emotion_confidence": 0.0, "error": str(exc)}
