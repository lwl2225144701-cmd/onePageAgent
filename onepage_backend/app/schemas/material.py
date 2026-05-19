from datetime import datetime

from pydantic import BaseModel


class MaterialResponse(BaseModel):
    id: str
    material_type: str
    style_tags: list[str] | None = None
    emotion_tags: list[str] | None = None
    scene_tags: list[str] | None = None
    file_url: str
    meta_info: dict | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class MaterialGroup(BaseModel):
    material_type: str
    items: list[MaterialResponse]


class RecommendResponse(BaseModel):
    groups: list[MaterialGroup]
