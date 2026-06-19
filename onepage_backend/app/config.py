from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ──
    APP_NAME: str = "onepage-api"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api"
    PUBLIC_API_BASE_URL: str = "/api"
    SECRET_KEY: str = "change-me"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
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
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    VISION_REVIEW_ENABLED: bool = True
    VISION_REVIEW_PROVIDER: str = "dashscope"
    VISION_REVIEW_MODEL: str = "qwen3.5-omni-flash"
    VISION_REVIEW_TIMEOUT_SECONDS: int = 10
    VISION_REVIEW_MAX_RETRIES: int = 1
    VISION_REVIEW_MAX_CANDIDATES: int = 8
    VISION_REVIEW_MODE: str = "best_effort"
    VISION_REVIEW_FAIL_OPEN: bool = False
    VISION_REVIEW_MAX_DATA_URL_BYTES: int = 8_000_000
    VISION_REVIEW_CONTACT_SHEET_MIME: str = "image/jpeg"
    VISION_REVIEW_CIRCUIT_BREAKER_ENABLED: bool = True
    VISION_REVIEW_CIRCUIT_BREAKER_THRESHOLD: int = 3
    VISION_REVIEW_CIRCUIT_BREAKER_COOLDOWN_SECONDS: int = 300

    # ── Weather ──
    WEATHER_API_URL: str = ""
    WEATHER_API_KEY: str = ""
    WEATHER_CACHE_TTL: int = 86400
    AMAP_WEATHER_MCP_URL: str = "http://127.0.0.1:8001/mcp"
    MCP_TOOL_TIMEOUT_SECONDS: int = 10
    DEFAULT_WEATHER_LOCATION: str = ""

    # ── Logging ──
    PIPELINE_LOG_LEVEL: str = "INFO"
    PIPELINE_DEBUG_TRACE: bool = False
    LOG_EXTERNAL_LIBRARIES: str = "WARNING"
    LOG_SSE_PROGRESS: bool = False
    LOG_FULL_CANDIDATES: bool = False
    LOG_MCP_PROTOCOL: bool = False

    # ── Rate Limit ──
    RATE_LIMIT_PER_MINUTE: int = 30

    # ── SSE ──
    SSE_TTL: int = 3600

    # ── Celery ──
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300
    CELERY_TASK_TIME_LIMIT: int = 600

    @field_validator("VISION_REVIEW_PROVIDER")
    @classmethod
    def validate_vision_review_provider(cls, value: str) -> str:
        provider = str(value or "").strip().lower()
        if provider not in {"dashscope", "rules"}:
            return "rules"
        return provider


settings = Settings()
