from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

from app.config import settings


class DashScopeVisionReviewError(RuntimeError):
    """Raised when the optional DashScope visual reviewer cannot produce JSON text."""


class VisionImageTooLargeError(DashScopeVisionReviewError):
    """Raised before a model call when the in-memory Data URL exceeds the configured cap."""


def build_image_data_url(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def validate_data_url_size(data_url: str, *, max_bytes: int | None = None) -> int:
    data_url_bytes = len(str(data_url or "").encode("utf-8"))
    limit = int(max_bytes or settings.VISION_REVIEW_MAX_DATA_URL_BYTES or 8_000_000)
    if data_url_bytes > limit:
        raise VisionImageTooLargeError(f"contact_sheet_data_url_too_large:{data_url_bytes}")
    return data_url_bytes


class DashScopeVisionReviewClient:
    """DashScope OpenAI-compatible streaming client for Step4.5 material review."""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        self.base_url = settings.DASHSCOPE_BASE_URL
        self.model = normalize_dashscope_vision_model(settings.VISION_REVIEW_MODEL)
        self.timeout = max(1, int(settings.VISION_REVIEW_TIMEOUT_SECONDS or 10))
        self.max_retries = max(0, int(settings.VISION_REVIEW_MAX_RETRIES or 1))
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except Exception as exc:  # pragma: no cover - depends on local optional dependency install
                raise DashScopeVisionReviewError("dashscope_openai_sdk_unavailable") from exc
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result
            self._client = None

    async def review_contact_sheet(
        self,
        *,
        prompt: str,
        contact_sheet_data_url: str,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise DashScopeVisionReviewError("missing_dashscope_api_key")

        last_reason = "unknown"
        for attempt in range(self.max_retries + 1):
            try:
                return await self._stream_review(
                    prompt=prompt,
                    contact_sheet_data_url=contact_sheet_data_url,
                    task_id=task_id,
                )
            except Exception as exc:
                retryable, reason = _retry_policy(exc)
                last_reason = reason
                if retryable and attempt < self.max_retries:
                    print(
                        f"VISION_REVIEW_CLIENT_RETRY task_id={task_id} attempt={attempt + 1} reason={reason}",
                        flush=True,
                    )
                    await self.close()
                    await asyncio.sleep(min(1.5, 0.4 * (2**attempt)))
                    continue
                raise DashScopeVisionReviewError(reason) from exc

        raise DashScopeVisionReviewError(last_reason)

    async def _stream_review(
        self,
        *,
        prompt: str,
        contact_sheet_data_url: str,
        task_id: str | None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": contact_sheet_data_url},
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
            stream=True,
            stream_options={"include_usage": True},
            temperature=0.1,
            extra_body={
                "modalities": ["text"],
                "enable_thinking": False,
            },
        )

        print(f"VISION_REVIEW_STREAM_STARTED task_id={task_id}", flush=True)
        content_parts: list[str] = []
        usage: Any | None = None
        async for chunk in stream:
            choices = getattr(chunk, "choices", None)
            if choices:
                delta = getattr(choices[0], "delta", None)
                text = getattr(delta, "content", None)
                if isinstance(text, str) and text:
                    content_parts.append(text)
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage is not None:
                usage = chunk_usage

        content = "".join(content_parts).strip()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        print(
            f"VISION_REVIEW_STREAM_DONE task_id={task_id} content_length={len(content)} elapsed_ms={elapsed_ms}",
            flush=True,
        )
        if not content:
            raise DashScopeVisionReviewError("dashscope_empty_response")
        return {
            "content": content,
            "usage": _usage_to_dict(usage),
            "elapsed_ms": elapsed_ms,
        }


def _usage_to_dict(usage: Any | None) -> dict[str, Any]:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return usage
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    result: dict[str, Any] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
        value = getattr(usage, key, None)
        if value is not None:
            result[key] = value
    return result


def normalize_dashscope_vision_model(model: str | None) -> str:
    value = str(model or "").strip()
    aliases = {
        "": "qwen3-omni-flash",
        "qwen3.5-omni-flash": "qwen3-omni-flash",
    }
    return aliases.get(value, value)


def _retry_policy(exc: Exception) -> tuple[bool, str]:
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)
    if status_code is not None:
        status = int(status_code)
        reason = f"dashscope_vision_http_{status}"
        if status in {400, 401, 403}:
            return False, reason
        if status in {408, 429, 500, 502, 503, 504}:
            return True, reason
        return False, reason

    name = exc.__class__.__name__.lower()
    text = str(exc).lower()
    if "timeout" in name or "timeout" in text:
        return True, "dashscope_vision_timeout"
    if "connect" in name or "connection" in text:
        return True, "dashscope_vision_connection_error"
    if isinstance(exc, DashScopeVisionReviewError):
        return False, str(exc) or "dashscope_vision_failed"
    return False, exc.__class__.__name__ or "dashscope_vision_failed"
