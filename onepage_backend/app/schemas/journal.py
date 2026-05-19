from datetime import datetime

from pydantic import BaseModel


class CreateJournalRequest(BaseModel):
    name: str
    cover_url: str | None = None
    settings: dict | None = None


class JournalResponse(BaseModel):
    id: str
    user_id: str
    name: str
    cover_url: str | None = None
    page_count: int = 0
    settings: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class JournalDetailResponse(JournalResponse):
    pages: list["PageBriefResponse"] = []


from app.schemas.page import PageBriefResponse
