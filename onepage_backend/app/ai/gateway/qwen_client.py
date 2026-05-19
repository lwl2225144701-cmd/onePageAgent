from app.ai.gateway.base import BaseModelClient
from app.config import settings


class QwenClient(BaseModelClient):
    def __init__(self):
        super().__init__(
            api_url=settings.QWEN_API_URL,
            api_key=settings.QWEN_API_KEY,
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
            # Return empty payload so upstream can fallback to another provider.
            return {}

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": "qwen-plus",
            "input": {"messages": full_messages},
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        }
        if response_format:
            payload["parameters"]["result_format"] = "json"

        return await self._request("POST", "/services/aigc/text-generation/generation", payload)

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> dict:
        return await self.call(messages, system_prompt, temperature, max_tokens, response_format)
