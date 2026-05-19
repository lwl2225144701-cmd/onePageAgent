from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class ElementDTO(BaseModel):
    element_type: str
    props_json: dict
    z_index: int = 0


class ElementResponse(BaseModel):
    id: str
    page_id: str
    element_type: str
    props_json: dict
    z_index: int
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class CreatePageRequest(BaseModel):
    journal_id: str
    title: str | None = None
    content_text: str | None = None
    layout_json: dict | None = None
    elements: list[ElementDTO] | None = None
    weather: dict | None = None
    mood: str | None = None
    page_date: str | None = None


class UpdatePageRequest(BaseModel):
    title: str | None = None
    content_text: str | None = None
    layout_json: dict | None = None
    elements: list[ElementDTO] | None = None
    weather: dict | None = None
    mood: str | None = None


class PageResponse(BaseModel):
    id: str
    journal_id: str
    user_id: str
    title: str | None = None
    content_text: str | None = None
    layout_json: dict | None = None
    thumbnail_url: str | None = None
    weather: dict | None = None
    mood: str | None = None
    page_date: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class PageDetailResponse(PageResponse):
    elements: list[ElementResponse] = []


class PageBriefResponse(BaseModel):
    id: str
    title: str | None = None
    thumbnail_url: str | None = None
    mood: str | None = None
    page_date: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True
