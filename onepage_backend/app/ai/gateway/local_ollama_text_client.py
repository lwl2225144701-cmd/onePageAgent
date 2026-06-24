from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings


class LocalOllamaTextError(RuntimeError):
    pass


class LocalOllamaTextClient:
    def __init__(self) -> None:
        self.base_url = str(settings.LOCAL_TEXT_LLM_BASE_URL or "").rstrip("/")
        self.model = str(settings.LOCAL_TEXT_LLM_MODEL or "").strip()
        self.timeout = max(1, int(settings.LOCAL_TEXT_LLM_TIMEOUT_SECONDS or 60))
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

    async def generate_json(
        self,
        *,
        prompt: str,
        system_prompt: str,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.base_url:
            raise LocalOllamaTextError("missing_local_text_llm_base_url")
        if not self.model:
            raise LocalOllamaTextError("missing_local_text_llm_model")
        started = time.perf_counter()
        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "format": "json",
                    "stream": False,
                    "keep_alive": "30m",
                    "options": {"temperature": 0.1, "num_predict": 220},
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LocalOllamaTextError("local_text_llm_timeout") from exc
        except httpx.ConnectError as exc:
            raise LocalOllamaTextError("local_text_llm_connection_error") from exc
        except httpx.HTTPStatusError as exc:
            raise LocalOllamaTextError(f"local_text_llm_http_{exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise LocalOllamaTextError("local_text_llm_http_error") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise LocalOllamaTextError("local_text_llm_invalid_response") from exc
        message = payload.get("message") if isinstance(payload, dict) else None
        content = str(message.get("content") or "").strip() if isinstance(message, dict) else ""
        if not content:
            raise LocalOllamaTextError("local_text_llm_empty_response")
        return {
            "content": content,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "usage": {
                key: payload[key]
                for key in ("prompt_eval_count", "eval_count", "total_duration", "load_duration")
                if payload.get(key) is not None
            },
            "task_id": task_id,
        }
