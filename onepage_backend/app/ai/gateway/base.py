import asyncio
from abc import ABC, abstractmethod

import httpx
import structlog

from app.config import settings
from app.core.exceptions import ModelAPIError, ModelTimeoutError

logger = structlog.get_logger(__name__)


class BaseModelClient(ABC):
    def __init__(self, api_url: str, api_key: str, timeout: int | None = None, max_retries: int | None = None):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout or settings.AI_REQUEST_TIMEOUT
        self.max_retries = max_retries or settings.AI_MAX_RETRIES
        self._http: httpx.AsyncClient | None = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.timeout)
        return self._http

    async def close(self):
        if self._http:
            await self._http.aclose()
            self._http = None

    async def _request(self, method: str, endpoint: str, payload: dict | None = None) -> dict:
        url = f"{self.api_url}{endpoint}"
        headers = self._build_headers()

        for attempt in range(self.max_retries + 1):
            try:
                resp = await self.http.request(method, url, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except httpx.TimeoutException:
                logger.warning("model_timeout", url=url, attempt=attempt)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise ModelTimeoutError(f"Request to {url} timed out after {self.timeout}s")
            except httpx.HTTPStatusError as e:
                logger.error("model_api_error", url=url, status=e.response.status_code, body=e.response.text[:500])
                if attempt < self.max_retries and e.response.status_code >= 500:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise ModelAPIError(f"API error: {e.response.status_code}")
            except Exception as e:
                logger.error("model_request_error", url=url, error=str(e))
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise ModelAPIError(str(e))

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @abstractmethod
    async def call(self, *args, **kwargs) -> dict:
        ...
