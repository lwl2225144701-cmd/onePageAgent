from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.common import UnifiedResponse
from app.schemas.export import ExportRequest, ExportTaskResponse
from app.services.export_service import ExportService

router = APIRouter()


@router.post("", response_model=UnifiedResponse[ExportTaskResponse])
async def create_export(
    body: ExportRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ExportService(db)
    task = await svc.create_export(user_id, body.page_id, body.format)

    try:
        from app.workers.export_tasks import run_export
        run_export.delay(task.task_id, body.page_id, body.format)
    except Exception:
        pass

    return UnifiedResponse(data=ExportTaskResponse(
        task_id=task.task_id,
        status=task.status,
        created_at=task.created_at,
    ))
