import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.serializers import to_material_group_response, to_material_response, to_paginated_response
from app.api.deps import get_current_user, get_db, get_redis
from app.config import settings
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
REPO_ROOT = Path(__file__).resolve().parents[4]
MATERIAL_SOURCE_ROOT = REPO_ROOT / "素材2.0"
HTML_IMAGE_SRC_RE = re.compile(rb"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)


@router.get("", response_model=UnifiedResponse[PaginatedResponse[MaterialResponse]])
async def list_materials(
    type: str | None = Query(None, alias="type"),
    style: str | None = None,
    emotion: str | None = None,
    scene: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    query: str | None = None,
    user_id: str = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = MaterialService(db)
    materials, total = await svc.list_materials(
        material_type=type, style=style, emotion=emotion, scene=scene, category=category, tag=tag, query=query, user_id=user_id,
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
        local_response = _serve_local_material_fallback(meta)
        if local_response is not None:
            return local_response
        raise HTTPException(status_code=404, detail="Material object not found")

    data = _read_material_object(object_name)
    if data is not None:
        response = _build_material_binary_response(data, mime_type)
        if response is not None:
            return response

    local_response = _serve_local_material_fallback(meta)
    if local_response is not None:
        return local_response
    raise HTTPException(status_code=404, detail="Material object not found")


def _extract_object_name_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    path = parsed.path.lstrip("/")
    bucket_prefix = "onepage-materials/"
    if not path.startswith(bucket_prefix):
        return None
    return path[len(bucket_prefix):]


def _read_material_object(object_name: str) -> bytes | None:
    clients = [get_minio()]
    if settings.MINIO_ENDPOINT.startswith(("127.0.0.1:", "localhost:")):
        clients.append(Minio(
            endpoint="training-minio:9000",
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        ))

    for client in clients:
        obj = None
        try:
            obj = client.get_object(settings.MINIO_BUCKET_MATERIALS, object_name)
            return obj.read()
        except Exception:
            continue
        finally:
            if obj is not None:
                obj.close()
                obj.release_conn()
    return None


def _serve_local_material_fallback(meta: dict) -> Response | None:
    asset_path = _find_local_material_path(meta)
    if asset_path is None:
        return None
    mime_type = mimetypes.guess_type(asset_path.name)[0] or meta.get("mime_type") or "application/octet-stream"
    return _build_material_binary_response(asset_path.read_bytes(), mime_type, max_age=86400)


def _build_material_binary_response(data: bytes, mime_type: str, max_age: int = 31536000) -> Response | RedirectResponse | None:
    embedded_url = _extract_embedded_image_url(data)
    if embedded_url:
        return RedirectResponse(embedded_url, status_code=302)
    if not _looks_like_image(data, mime_type):
        return None
    return Response(
        content=data,
        media_type=mime_type,
        headers={"Cache-Control": f"public, max-age={max_age}, immutable"},
    )


def _extract_embedded_image_url(data: bytes) -> str | None:
    head = data[:4096].lstrip().lower()
    if not head.startswith(b"<html") and b"<img" not in head:
        return None
    match = HTML_IMAGE_SRC_RE.search(data[:8192])
    if not match:
        return None
    url = match.group(1).decode("utf-8", errors="ignore").strip()
    return url if url.startswith(("http://", "https://")) else None


def _looks_like_image(data: bytes, mime_type: str) -> bool:
    head = data[:2048].lstrip()
    lowered = head.lower()
    if mime_type == "image/svg+xml" or lowered.startswith(b"<?xml") or b"<svg" in lowered:
        return b"<svg" in lowered
    return (
        data.startswith(b"\xff\xd8\xff") or
        data.startswith(b"\x89PNG\r\n\x1a\n") or
        (data.startswith(b"RIFF") and b"WEBP" in data[:16]) or
        data.startswith((b"GIF87a", b"GIF89a"))
    )


def _find_local_material_path(meta: dict) -> Path | None:
    candidates: list[Path] = []
    for key in ("origin_path", "filepath"):
        value = str(meta.get(key) or "").strip()
        if value:
            candidates.append(Path(value))
    target_path = str(meta.get("target_path") or "").strip()
    if target_path:
        candidates.append(MATERIAL_SOURCE_ROOT / target_path)

    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if resolved.is_file() and resolved.is_relative_to(MATERIAL_SOURCE_ROOT.resolve()):
            return resolved
    return None
