from __future__ import annotations

from typing import Protocol

from app.ai.gateway.dashscope_vision_client import DashScopeVisionReviewClient, normalize_dashscope_vision_model
from app.ai.gateway.local_ollama_vl_client import LocalOllamaVisionClient
from app.config import settings


class VisionReviewClient(Protocol):
    model: str

    async def review_contact_sheet(
        self,
        *,
        prompt: str,
        contact_sheet_data_url: str,
        task_id: str | None = None,
    ) -> dict: ...

    async def close(self) -> None: ...


def create_vision_review_client() -> VisionReviewClient | None:
    provider = settings.VISION_REVIEW_PROVIDER
    if provider == "dashscope":
        return DashScopeVisionReviewClient()
    if provider == "local_ollama":
        return LocalOllamaVisionClient()
    return None


def get_vision_review_model() -> str:
    if settings.VISION_REVIEW_PROVIDER == "dashscope":
        return normalize_dashscope_vision_model(settings.VISION_REVIEW_MODEL)
    if settings.VISION_REVIEW_PROVIDER == "local_ollama":
        return str(settings.LOCAL_VL_MODEL or "").strip()
    return "rules"
