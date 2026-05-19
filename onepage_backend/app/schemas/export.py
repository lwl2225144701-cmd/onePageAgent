from datetime import datetime

from pydantic import BaseModel


class ExportRequest(BaseModel):
    page_id: str
    format: str = "png"


class ExportTaskResponse(BaseModel):
    task_id: str
    status: str
    created_at: datetime | None = None
