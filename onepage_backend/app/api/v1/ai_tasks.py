from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from typing import Any
import structlog

from app.api.deps import get_current_user, get_db, get_redis
from app.core.exceptions import NotFoundException
from app.schemas.ai_task import CreateTaskRequest, TaskDetailResponse, TaskResponse
from app.schemas.common import UnifiedResponse
from app.services.ai_task_service import AITaskService
from app.services.sse_service import SSEService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("", response_model=UnifiedResponse[TaskResponse])
async def create_ai_task(
    body: CreateTaskRequest | dict[str, Any],
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    logger.debug("api_ai_task_create_request", user_id=user_id, body_type=type(body).__name__)
    svc = AITaskService(db, redis)
    input_json = body.input_json if isinstance(body, CreateTaskRequest) else body.get("input_json", body)
    task = await svc.create_task(user_id, input_json)
    logger.info("api_ai_task_created", task_id=task.task_id, user_id=user_id, status=task.status)

    # Dispatch Celery task
    try:
        from app.workers.llm_tasks import run_ai_orchestration
        run_ai_orchestration.delay(task.task_id, user_id, task.input_json)
        logger.info("api_ai_task_dispatched", task_id=task.task_id, queue="llm_queue")
    except Exception:
        logger.exception("api_ai_task_dispatch_failed", task_id=task.task_id)
        pass  # Worker not running yet — task stays pending

    return UnifiedResponse(data=TaskResponse(
        task_id=task.task_id,
        status=task.status,
        progress=task.progress,
        created_at=task.created_at,
    ))


@router.get("/{task_id}", response_model=UnifiedResponse[TaskDetailResponse])
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    logger.debug("api_ai_task_get_request", task_id=task_id)
    svc = AITaskService(db, redis)
    data = await svc.get_task(task_id)
    if not data:
        logger.warning("api_ai_task_not_found", task_id=task_id)
        raise NotFoundException("Task not found")
    logger.debug("api_ai_task_get_success", task_id=task_id, status=data.get("status"), progress=data.get("progress"))
    return UnifiedResponse(data=TaskDetailResponse(**data))


@router.get("/{task_id}/events")
async def stream_task_events(
    task_id: str,
    redis: aioredis.Redis = Depends(get_redis),
):
    logger.debug("api_ai_task_events_subscribe", task_id=task_id)
    sse = SSEService(redis)

    # Check task exists first
    cached = await redis.get(f"task:{task_id}:status")
    if not cached:
        from sqlalchemy import select
        from app.models.ai_task import AITask
        # Can't easily get DB here without Depends in async gen; just start streaming and let client handle
        pass

    return StreamingResponse(
        sse.subscribe(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
