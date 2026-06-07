from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ──
    APP_NAME: str = "onepage-api"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api"
    PUBLIC_API_BASE_URL: str = "http://127.0.0.1:8000/api"
    SECRET_KEY: str = "change-me"
    ANONYMOUS_USER_HEADER: str = "X-Anonymous-User-Id"
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png", "image/webp", "image/svg+xml"]
    ALLOWED_AUDIO_TYPES: list[str] = ["audio/wav", "audio/mp3", "audio/m4a", "audio/webm"]

    # ── Database ──
    DATABASE_URL: str = "postgresql+asyncpg://training:training123@training-postgres:5432/onepage"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # ── Redis ──
    REDIS_URL: str = "redis://training-redis:6379/2"
    CELERY_BROKER_URL: str = "redis://training-redis:6379/3"
    CELERY_RESULT_BACKEND: str = "redis://training-redis:6379/4"

    # ── MinIO ──
    MINIO_ENDPOINT: str = "training-minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_UPLOADS: str = "onepage-uploads"
    MINIO_BUCKET_MATERIALS: str = "onepage-materials"
    MINIO_SECURE: bool = False

    # ── AI Models ──
    SENSEVOICE_API_URL: str = ""
    SENSEVOICE_API_KEY: str = ""
    QWEN_VL_API_URL: str = ""
    QWEN_VL_API_KEY: str = ""
    DEEPSEEK_API_URL: str = "https://api.xiaomimimo.com/v1"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "mimo-v2.5-pro"
    QWEN_API_URL: str = "https://dashscope.aliyuncs.com/api/v1"
    QWEN_API_KEY: str = ""
    AI_REQUEST_TIMEOUT: int = 60
    AI_MAX_RETRIES: int = 3

    # ── Weather ──
    WEATHER_API_URL: str = ""
    WEATHER_API_KEY: str = ""
    WEATHER_CACHE_TTL: int = 86400

    # ── Rate Limit ──
    RATE_LIMIT_PER_MINUTE: int = 30

    # ── SSE ──
    SSE_TTL: int = 3600

    # ── Celery ──
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300
    CELERY_TASK_TIME_LIMIT: int = 600


settings = Settings()
