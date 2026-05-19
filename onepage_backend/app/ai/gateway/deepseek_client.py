from app.ai.gateway.base import BaseModelClient
from app.config import settings


class DeepSeekClient(BaseModelClient):
    def __init__(self):
        super().__init__(
            api_url=settings.DEEPSEEK_API_URL,
            api_key=settings.DEEPSEEK_API_KEY,
        )

    async def call(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> dict:
        if not self.api_key:
            # Return empty payload so pipeline can fallback gracefully.
            return {}

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": settings.DEEPSEEK_MODEL,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        return await self._request("POST", "/chat/completions", payload)

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> dict:
        return await self.call(messages, system_prompt, temperature, max_tokens, response_format)
