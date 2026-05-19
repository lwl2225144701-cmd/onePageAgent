from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.common import PaginatedResponse, PaginationMeta, UnifiedResponse
from app.schemas.material import MaterialResponse, MaterialGroup
from app.services.material_service import MaterialService

router = APIRouter()


@router.get("", response_model=UnifiedResponse[PaginatedResponse[MaterialResponse]])
async def list_materials(
    type: str | None = Query(None, alias="type"),
    style: str | None = None,
    emotion: str | None = None,
    scene: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = MaterialService(db)
    materials, total = await svc.list_materials(
        material_type=type, style=style, emotion=emotion, scene=scene,
        page=page, size=size,
    )
    items = [
        MaterialResponse(
            id=str(m.id), material_type=m.material_type,
            style_tags=m.style_tags, emotion_tags=m.emotion_tags,
            scene_tags=m.scene_tags, file_url=m.file_url,
            metadata=m.meta_info, created_at=m.created_at,
        )
        for m in materials
    ]
    total_pages = (total + size - 1) // size if total > 0 else 0
    return UnifiedResponse(data=PaginatedResponse(
        data=items,
        pagination=PaginationMeta(page=page, size=size, total=total, total_pages=total_pages),
    ))


@router.get("/recommend", response_model=UnifiedResponse[list[MaterialGroup]])
async def recommend_materials(
    style: str | None = None,
    emotion: str | None = None,
    scene: str | None = None,
    weather: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    svc = MaterialService(db)
    groups = await svc.recommend(style=style, emotion=emotion, scene=scene, weather=weather)
    result = [
        MaterialGroup(
            material_type=g["material_type"],
            items=[
                MaterialResponse(
                    id=str(m.id), material_type=m.material_type,
                    style_tags=m.style_tags, emotion_tags=m.emotion_tags,
                    scene_tags=m.scene_tags, file_url=m.file_url,
                    metadata=m.meta_info, created_at=m.created_at,
                )
                for m in g["items"]
            ],
        )
        for g in groups
    ]
    return UnifiedResponse(data=result)
