from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from app.config import settings


class LocalOllamaVisionError(RuntimeError):
    """Raised when the local Ollama visual reviewer cannot return text."""


class LocalOllamaVisionClient:
    def __init__(self) -> None:
        self.base_url = str(settings.LOCAL_VL_BASE_URL or "").rstrip("/")
        self.model = str(settings.LOCAL_VL_MODEL or "").strip()
        self.timeout = max(1, int(settings.LOCAL_VL_TIMEOUT_SECONDS or 120))
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def review_contact_sheet(
        self,
        *,
        prompt: str,
        contact_sheet_data_url: str,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.base_url:
            raise LocalOllamaVisionError("missing_local_vl_base_url")
        if not self.model:
            raise LocalOllamaVisionError("missing_local_vl_model")

        image_base64 = _extract_base64_image(contact_sheet_data_url)
        started = time.perf_counter()
        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [image_base64],
                        }
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1},
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LocalOllamaVisionError("local_ollama_vision_timeout") from exc
        except httpx.ConnectError as exc:
            raise LocalOllamaVisionError("local_ollama_vision_connection_error") from exc
        except httpx.HTTPStatusError as exc:
            raise LocalOllamaVisionError(f"local_ollama_vision_http_{exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise LocalOllamaVisionError("local_ollama_vision_http_error") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise LocalOllamaVisionError("local_ollama_vision_invalid_json") from exc
        message = payload.get("message") if isinstance(payload, dict) else None
        content = str(message.get("content") or "").strip() if isinstance(message, dict) else ""
        if not content:
            raise LocalOllamaVisionError("local_ollama_vision_empty_response")
        return {
            "content": content,
            "usage": _usage_from_payload(payload),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }


def _extract_base64_image(data_url: str) -> str:
    header, separator, encoded = str(data_url or "").partition(",")
    if not separator or not header.startswith("data:image/") or ";base64" not in header or not encoded:
        raise LocalOllamaVisionError("local_ollama_invalid_image_data_url")
    try:
        base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise LocalOllamaVisionError("local_ollama_invalid_image_base64") from exc
    return encoded


def _usage_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in ("prompt_eval_count", "eval_count", "total_duration", "load_duration")
        if payload.get(key) is not None
    }
