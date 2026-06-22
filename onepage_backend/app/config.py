from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILES = (BACKEND_DIR / ".env.example", PROJECT_ROOT / ".env", BACKEND_DIR / ".env")
VISION_REVIEW_PROVIDERS = {"dashscope", "local_ollama", "rules"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──
    APP_NAME: str
    DEBUG: bool
    API_V1_PREFIX: str
    PUBLIC_API_BASE_URL: str
    SECRET_KEY: str
    CORS_ALLOWED_ORIGINS: str
    ANONYMOUS_USER_HEADER: str
    MAX_UPLOAD_SIZE_MB: int
    ALLOWED_IMAGE_TYPES: list[str]
    ALLOWED_AUDIO_TYPES: list[str]
    LAYOUT_ENGINE_VERSION: str = "v2"
    BUILD_COMMIT_SHA: str = "development"

    # ── Database ──
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int
    DATABASE_MAX_OVERFLOW: int

    # ── Redis ──
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # ── MinIO ──
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET_UPLOADS: str
    MINIO_BUCKET_MATERIALS: str
    MINIO_SECURE: bool

    # ── AI Models ──
    SENSEVOICE_API_URL: str
    SENSEVOICE_API_KEY: str
    QWEN_VL_API_URL: str
    QWEN_VL_API_KEY: str
    DEEPSEEK_API_URL: str
    DEEPSEEK_API_KEY: str
    DEEPSEEK_MODEL: str
    QWEN_API_URL: str
    QWEN_API_KEY: str
    AI_REQUEST_TIMEOUT: int
    AI_MAX_RETRIES: int
    DASHSCOPE_API_KEY: str
    DASHSCOPE_BASE_URL: str
    VISION_REVIEW_ENABLED: bool
    VISION_REVIEW_PROVIDER: str
    VISION_REVIEW_MODEL: str
    VISION_REVIEW_TIMEOUT_SECONDS: int
    VISION_REVIEW_MAX_RETRIES: int
    VISION_REVIEW_MAX_CANDIDATES: int
    VISION_REVIEW_MODE: str
    VISION_REVIEW_FAIL_OPEN: bool
    VISION_REVIEW_MAX_DATA_URL_BYTES: int
    VISION_REVIEW_CONTACT_SHEET_MIME: str
    VISION_REVIEW_CIRCUIT_BREAKER_ENABLED: bool
    VISION_REVIEW_CIRCUIT_BREAKER_THRESHOLD: int
    VISION_REVIEW_CIRCUIT_BREAKER_COOLDOWN_SECONDS: int
    LOCAL_VL_BASE_URL: str = "http://127.0.0.1:11434"
    LOCAL_VL_MODEL: str = "qwen2.5-vl:3b"
    LOCAL_VL_TIMEOUT_SECONDS: int = 120

    # ── Weather ──
    AMAP_WEB_SERVICE_KEY: str
    AMAP_REVERSE_GEOCODE_URL: str
    AMAP_WEATHER_URL: str
    WEATHER_CACHE_TTL: int
    AMAP_WEATHER_MCP_URL: str
    MCP_TOOL_TIMEOUT_SECONDS: int
    DEFAULT_WEATHER_LOCATION: str

    # ── Logging ──
    PIPELINE_LOG_LEVEL: str
    PIPELINE_DEBUG_TRACE: bool
    LOG_EXTERNAL_LIBRARIES: str
    LOG_SSE_PROGRESS: bool
    LOG_FULL_CANDIDATES: bool
    LOG_MCP_PROTOCOL: bool

    # ── Rate Limit ──
    RATE_LIMIT_PER_MINUTE: int

    # ── SSE ──
    SSE_TTL: int

    # ── Celery ──
    CELERY_TASK_SOFT_TIME_LIMIT: int
    CELERY_TASK_TIME_LIMIT: int

    @field_validator("VISION_REVIEW_PROVIDER")
    @classmethod
    def validate_vision_review_provider(cls, value: str) -> str:
        provider = str(value or "").strip().lower()
        if provider not in VISION_REVIEW_PROVIDERS:
            return "rules"
        return provider

    @field_validator("LAYOUT_ENGINE_VERSION")
    @classmethod
    def validate_layout_engine_version(cls, value: str) -> str:
        return "v2" if str(value or "").strip().lower() == "v2" else "v1"


settings = Settings()
