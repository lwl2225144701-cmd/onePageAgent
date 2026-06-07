import mimetypes
from urllib.parse import urlparse

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.serializers import to_material_group_response, to_material_response, to_paginated_response
from app.api.deps import get_current_user, get_db, get_redis
from app.core.minio import get_minio
from app.schemas.common import PaginatedResponse, UnifiedResponse
from app.schemas.material import (
    MaterialFavoriteRequest,
    MaterialGroup,
    MaterialResponse,
    MaterialUploadSessionCompleteRequest,
    MaterialUploadSessionCreateRequest,
    MaterialUploadSessionCreateResponse,
)
from app.services.material_service import MaterialService, MaterialUploadService

router = APIRouter()


@router.get("", response_model=UnifiedResponse[PaginatedResponse[MaterialResponse]])
async def list_materials(
    type: str | None = Query(None, alias="type"),
    style: str | None = None,
    emotion: str | None = None,
    scene: str | None = None,
    user_id: str = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = MaterialService(db)
    materials, total = await svc.list_materials(
        material_type=type, style=style, emotion=emotion, scene=scene, user_id=user_id,
        page=page, size=size,
    )
    items = [to_material_response(item, user_id) for item in materials]
    return UnifiedResponse(data=to_paginated_response(items=items, page=page, size=size, total=total))


@router.get("/favorites", response_model=UnifiedResponse[PaginatedResponse[MaterialResponse]])
async def list_favorite_materials(
    type: str | None = Query(None, alias="type"),
    user_id: str = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = MaterialService(db)
    materials, total = await svc.list_favorites(user_id=user_id, material_type=type, page=page, size=size)
    items = [to_material_response(item, user_id) for item in materials]
    return UnifiedResponse(data=to_paginated_response(items=items, page=page, size=size, total=total))


@router.get("/recent", response_model=UnifiedResponse[PaginatedResponse[MaterialResponse]])
async def list_recent_materials(
    type: str | None = Query(None, alias="type"),
    user_id: str = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = MaterialService(db)
    materials, total = await svc.list_recent(user_id=user_id, material_type=type, page=page, size=size)
    items = [to_material_response(item, user_id) for item in materials]
    return UnifiedResponse(data=to_paginated_response(items=items, page=page, size=size, total=total))


@router.get("/recommend", response_model=UnifiedResponse[list[MaterialGroup]])
async def recommend_materials(
    style: str | None = None,
    emotion: str | None = None,
    scene: str | None = None,
    weather: str | None = None,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = MaterialService(db)
    groups = await svc.recommend(style=style, emotion=emotion, scene=scene, weather=weather, user_id=user_id)
    result = [to_material_group_response(group, user_id) for group in groups]
    return UnifiedResponse(data=result)


@router.post("/upload/sessions", response_model=UnifiedResponse[MaterialUploadSessionCreateResponse])
async def create_upload_session(
    body: MaterialUploadSessionCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    svc = MaterialUploadService(db, redis)
    session = await svc.create_upload_session(
        user_id=user_id,
        file_name=body.file_name,
        file_size=body.file_size,
        mime_type=body.mime_type,
        material_type=body.material_type,
        category=body.category,
        tags=body.tags,
        visibility=body.visibility,
    )
    return UnifiedResponse(data=MaterialUploadSessionCreateResponse(**session))


@router.post("/upload/sessions/complete", response_model=UnifiedResponse[MaterialResponse])
async def complete_upload_session(
    body: MaterialUploadSessionCompleteRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    svc = MaterialUploadService(db, redis)
    m = await svc.complete_upload_session(user_id=user_id, session_id=body.session_id)
    return UnifiedResponse(data=to_material_response(m, user_id))


@router.delete("/upload/sessions/{session_id}", response_model=UnifiedResponse[dict])
async def cancel_upload_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    svc = MaterialUploadService(db, redis)
    await svc.cancel_upload_session(user_id=user_id, session_id=session_id)
    return UnifiedResponse(data={"ok": True})


@router.post("/{material_id}/favorite", response_model=UnifiedResponse[MaterialResponse])
async def set_material_favorite(
    material_id: str,
    body: MaterialFavoriteRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = MaterialService(db)
    material = await svc.set_favorite(material_id=material_id, user_id=user_id, is_favorite=body.is_favorite)
    return UnifiedResponse(data=to_material_response(material, user_id))


@router.post("/{material_id}/use", response_model=UnifiedResponse[MaterialResponse])
async def mark_material_used(
    material_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = MaterialService(db)
    material = await svc.mark_used(material_id=material_id, user_id=user_id)
    return UnifiedResponse(data=to_material_response(material, user_id))


@router.get("/{material_id}/asset")
async def get_material_asset(
    material_id: str,
    anonymous_user_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await _serve_material_binary(material_id=material_id, variant="asset", user_id=anonymous_user_id, db=db)


@router.get("/{material_id}/preview")
async def get_material_preview(
    material_id: str,
    anonymous_user_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await _serve_material_binary(material_id=material_id, variant="preview", user_id=anonymous_user_id, db=db)


async def _serve_material_binary(*, material_id: str, variant: str, user_id: str | None, db: AsyncSession) -> Response:
    svc = MaterialService(db)
    material = await svc.get_visible_material(material_id=material_id, user_id=user_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")

    meta = material.meta_info or {}
    target_url = meta.get("preview_url") if variant == "preview" and meta.get("preview_url") else material.file_url
    mime_type = mimetypes.guess_type(str(target_url))[0] or meta.get("mime_type") or "application/octet-stream"
    object_name = _extract_object_name_from_url(str(target_url))
    if not object_name:
        raise HTTPException(status_code=404, detail="Material object not found")

    obj = get_minio().get_object("onepage-materials", object_name)
    try:
        data = obj.read()
    finally:
        obj.close()
        obj.release_conn()
    return Response(
        content=data,
        media_type=mime_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


def _extract_object_name_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    path = parsed.path.lstrip("/")
    bucket_prefix = "onepage-materials/"
    if not path.startswith(bucket_prefix):
        return None
    return path[len(bucket_prefix):]
