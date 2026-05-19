from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.common import UnifiedResponse
from app.schemas.upload import UploadResponse
from app.services.upload_service import UploadService

router = APIRouter()


@router.post("/image", response_model=UnifiedResponse[UploadResponse])
async def upload_image(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UploadService(db)
    asset = await svc.upload_image(file, user_id)
    return UnifiedResponse(data=UploadResponse(
        file_id=str(asset.id),
        file_url=asset.file_url,
        file_name=asset.file_name,
        file_size=asset.file_size,
        mime_type=asset.mime_type,
        created_at=asset.created_at,
    ))


@router.post("/audio", response_model=UnifiedResponse[UploadResponse])
async def upload_audio(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UploadService(db)
    asset = await svc.upload_audio(file, user_id)
    return UnifiedResponse(data=UploadResponse(
        file_id=str(asset.id),
        file_url=asset.file_url,
        file_name=asset.file_name,
        file_size=asset.file_size,
        mime_type=asset.mime_type,
        created_at=asset.created_at,
    ))
