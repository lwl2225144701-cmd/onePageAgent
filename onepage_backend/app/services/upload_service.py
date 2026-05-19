import os
import uuid
from datetime import date

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ValidationException, StorageException
from app.core.minio import minio_upload_data
from app.models.upload_asset import UploadAsset


class UploadService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_image(self, file: UploadFile, user_id: str) -> UploadAsset:
        self._validate_file(file, settings.ALLOWED_IMAGE_TYPES)
        return await self._save(file, user_id, "image")

    async def upload_audio(self, file: UploadFile, user_id: str) -> UploadAsset:
        self._validate_file(file, settings.ALLOWED_AUDIO_TYPES)
        return await self._save(file, user_id, "audio")

    def _validate_file(self, file: UploadFile, allowed_types: list[str]):
        if file.content_type not in allowed_types:
            raise ValidationException(f"Unsupported file type: {file.content_type}")
        if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise ValidationException(f"File too large, max {settings.MAX_UPLOAD_SIZE_MB}MB")

    async def _save(self, file: UploadFile, user_id: str, asset_type: str) -> UploadAsset:
        content = await file.read()
        file_size = len(content)
        ext = os.path.splitext(file.filename or "file")[1]
        object_name = f"{user_id}/{date.today().isoformat()}/{uuid.uuid4().hex}{ext}"

        bucket = settings.MINIO_BUCKET_UPLOADS
        file_url = minio_upload_data(bucket, object_name, content, file.content_type or "application/octet-stream", file_size)

        asset = UploadAsset(
            user_id=user_id,
            asset_type=asset_type,
            file_url=file_url,
            file_name=file.filename or "unknown",
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
        )
        self.db.add(asset)
        await self.db.flush()
        await self.db.refresh(asset)
        return asset
