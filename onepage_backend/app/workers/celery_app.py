from celery import Celery

from app.config import settings
from app.core.logging import setup_logging

setup_logging(settings.DEBUG)

app = Celery(
    "onepage",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.voice_tasks",
        "app.workers.image_tasks",
        "app.workers.llm_tasks",
        "app.workers.export_tasks",
    ],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=True,
    worker_redirect_stdouts_level="INFO",
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_routes={
        "app.workers.voice_tasks.*": {"queue": "voice_queue"},
        "app.workers.image_tasks.*": {"queue": "image_queue"},
        "app.workers.llm_tasks.*": {"queue": "llm_queue"},
        "app.workers.export_tasks.*": {"queue": "export_queue"},
    },
)

# Keep autodiscover for compatibility; explicit include above is authoritative.
app.autodiscover_tasks(["app.workers"])

# Import signals to register them without shadowing the Celery `app` variable.
from app.workers import signals as _signals  # noqa: F401, E402

# Explicitly import task modules to guarantee registration in all start modes.
from app.workers import voice_tasks as _voice_tasks  # noqa: F401, E402
from app.workers import image_tasks as _image_tasks  # noqa: F401, E402
from app.workers import llm_tasks as _llm_tasks  # noqa: F401, E402
from app.workers import export_tasks as _export_tasks  # noqa: F401, E402
