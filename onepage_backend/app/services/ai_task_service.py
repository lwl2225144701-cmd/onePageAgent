import json
import uuid
import structlog

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ai_task import AITask

logger = structlog.get_logger(__name__)


class AITaskService:
    def __init__(self, db: AsyncSession, redis_client: aioredis.Redis | None = None):
        self.db = db
        self.redis = redis_client

    async def create_task(self, user_id: str, input_json: dict) -> AITask:
        task_id = uuid.uuid4().hex[:12]
        logger.debug("service_ai_task_create_start", task_id=task_id, user_id=user_id)
        prepared_input = dict(input_json) if isinstance(input_json, dict) else {}
        environment = prepared_input.get("environment_context")
        environment = environment if isinstance(environment, dict) else {}
        logger.info(
            "AI_ENVIRONMENT_CONTEXT_REUSED",
            task_id=task_id,
            city=environment.get("city"),
            weather=environment.get("weather") or "unknown",
        )
        task = AITask(
            task_id=task_id,
            user_id=user_id,
            status="pending",
            progress=0,
            input_json=prepared_input,
        )
        self.db.add(task)
        await self.db.flush()
        logger.debug("service_ai_task_flushed", task_id=task_id)

        if self.redis:
            await self.redis.setex(
                f"task:{task_id}:status",
                settings.SSE_TTL,
                json.dumps({"status": "pending", "progress": 0}, ensure_ascii=False),
            )
            logger.debug("service_ai_task_cached_pending", task_id=task_id)

        # Defer Celery dispatch to route layer (avoids circular import)
        await self.db.refresh(task)
        logger.info("service_ai_task_create_done", task_id=task_id, status=task.status)
        return task

    async def get_task(self, task_id: str) -> dict | None:
        cached_data: dict | None = None
        if self.redis:
            cached = await self.redis.get(f"task:{task_id}:status")
            if cached:
                cached_data = json.loads(cached)
                logger.debug("service_ai_task_cache_hit", task_id=task_id, status=cached_data.get("status"), progress=cached_data.get("progress"))
            else:
                logger.debug("service_ai_task_cache_miss", task_id=task_id)

        q = select(AITask).where(AITask.task_id == task_id)
        task = (await self.db.execute(q)).scalar_one_or_none()
        if not task:
            logger.warning("service_ai_task_db_not_found", task_id=task_id, has_cache=bool(cached_data))
            return cached_data

        data = {
            "task_id": task.task_id,
            "user_id": task.user_id,
            "status": task.status,
            "progress": task.progress,
            "input_json": task.input_json,
            "result_json": task.result_json,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }

        if cached_data:
            data["status"] = cached_data.get("status", data["status"])
            data["progress"] = cached_data.get("progress", data["progress"])
        logger.debug("service_ai_task_get_done", task_id=task_id, status=data["status"], progress=data["progress"])
        return data
