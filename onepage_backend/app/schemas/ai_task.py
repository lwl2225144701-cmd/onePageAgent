from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    input_json: dict = Field(..., description="User input: text, image_urls, audio_url, mood, weather")


class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int = 0
    created_at: datetime | None = None


class TaskDetailResponse(BaseModel):
    task_id: str
    user_id: str
    status: str
    progress: int
    input_json: dict
    result_json: dict | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class SSEProgressEvent(BaseModel):
    task_id: str
    step: int
    step_name: str
    status: str
    progress: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
