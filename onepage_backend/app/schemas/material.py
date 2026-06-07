from datetime import datetime

from pydantic import BaseModel, Field


class MaterialResponse(BaseModel):
    id: str
    material_type: str
    style_tags: list[str] | None = None
    emotion_tags: list[str] | None = None
    scene_tags: list[str] | None = None
    file_url: str
    preview_url: str | None = None
    raw_file_url: str | None = None
    mime_type: str | None = None
    meta_info: dict | None = None
    is_favorite: bool = False
    last_used_at: datetime | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class MaterialGroup(BaseModel):
    material_type: str
    items: list[MaterialResponse]


class RecommendResponse(BaseModel):
    groups: list[MaterialGroup]


class MaterialUploadSessionCreateRequest(BaseModel):
    file_name: str
    file_size: int = Field(..., gt=0)
    mime_type: str
    material_type: str
    category: str
    tags: list[str] = Field(default_factory=list)
    visibility: str = "private"


class MaterialUploadSessionCreateResponse(BaseModel):
    session_id: str
    upload_id: str
    object_key: str
    chunk_size: int
    total_parts: int
    part_urls: list[str]
    expires_at: str


class MaterialUploadSessionCompleteRequest(BaseModel):
    session_id: str


class MaterialFavoriteRequest(BaseModel):
    is_favorite: bool
