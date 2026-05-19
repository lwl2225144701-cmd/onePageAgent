from minio import Minio

from app.config import settings

_minio_client: Minio | None = None


def get_minio() -> Minio:
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _minio_client


def minio_upload_file(bucket: str, object_name: str, file_path: str, content_type: str) -> str:
    client = get_minio()
    client.fput_object(bucket, object_name, file_path, content_type=content_type)
    return f"{'https' if settings.MINIO_SECURE else 'http'}://{settings.MINIO_ENDPOINT}/{bucket}/{object_name}"


def minio_upload_data(bucket: str, object_name: str, data: bytes, content_type: str, size: int) -> str:
    import io
    client = get_minio()
    client.put_object(bucket, object_name, io.BytesIO(data), length=size, content_type=content_type)
    return f"{'https' if settings.MINIO_SECURE else 'http'}://{settings.MINIO_ENDPOINT}/{bucket}/{object_name}"
