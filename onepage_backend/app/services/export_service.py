import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_task import AITask


class ExportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_export(self, user_id: str, page_id: str, fmt: str = "png") -> AITask:
        task_id = uuid.uuid4().hex[:12]
        task = AITask(
            task_id=task_id,
            user_id=user_id,
            status="pending",
            progress=0,
            input_json={"page_id": page_id, "format": fmt},
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return task
