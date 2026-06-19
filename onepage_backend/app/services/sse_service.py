import asyncio
import json
from datetime import datetime
import structlog

import redis.asyncio as aioredis

from app.config import settings

logger = structlog.get_logger(__name__)


class SSEService:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def publish_progress(self, task_id: str, step: int, step_name: str, status: str, progress: int):
        if settings.LOG_SSE_PROGRESS:
            logger.debug("sse_publish_start", task_id=task_id, step=step, step_name=step_name, status=status, progress=progress)
        event_data = json.dumps(
            {
                "task_id": task_id,
                "step": step,
                "step_name": step_name,
                "status": status,
                "progress": progress,
                "timestamp": datetime.utcnow().isoformat(),
            },
            ensure_ascii=False,
        )
        await self.redis.publish(f"sse:{task_id}", event_data)
        await self.redis.setex(
            f"task:{task_id}:status",
            settings.SSE_TTL,
            json.dumps({"status": status, "progress": progress, "step": step, "step_name": step_name}, ensure_ascii=False),
        )
        if settings.LOG_SSE_PROGRESS:
            logger.debug("sse_publish_done", task_id=task_id, step=step, status=status, progress=progress)

    async def subscribe(self, task_id: str):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(f"sse:{task_id}")
        logger.debug("sse_subscribe_start", task_id=task_id)

        start_time = asyncio.get_event_loop().time()

        try:
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > settings.SSE_TTL:
                    logger.warning("sse_subscribe_timeout", task_id=task_id, elapsed=elapsed)
                    timeout_data = json.dumps(
                        {"task_id": task_id, "status": "timeout", "progress": 0, "step": 0, "step_name": ""},
                        ensure_ascii=False,
                    )
                    yield f"data: {timeout_data}\n\n"
                    break

                message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0), timeout=30)

                if message and message.get("type") == "message":
                    data = message["data"]
                    logger.debug("sse_subscribe_message", task_id=task_id, payload_size=len(data))
                    yield f"data: {data}\n\n"
                    parsed = json.loads(data)
                    if parsed.get("status") in ("completed", "failed"):
                        logger.debug("sse_subscribe_terminal_event", task_id=task_id, status=parsed.get("status"))
                        break
                else:
                    yield ": heartbeat\n\n"

        except asyncio.TimeoutError:
            logger.warning("sse_subscribe_asyncio_timeout", task_id=task_id)
            yield ": heartbeat\n\n"
        finally:
            await pubsub.unsubscribe(f"sse:{task_id}")
            await pubsub.close()
            logger.debug("sse_subscribe_closed", task_id=task_id)
