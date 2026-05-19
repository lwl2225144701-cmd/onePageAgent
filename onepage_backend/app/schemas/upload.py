from datetime import datetime

from pydantic import BaseModel


class UploadResponse(BaseModel):
    file_id: str
    file_url: str
    file_name: str
    file_size: int
    mime_type: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True
