from app.ai.gateway.base import BaseModelClient
from app.config import settings


class QwenVLClient(BaseModelClient):
    def __init__(self):
        super().__init__(
            api_url=settings.QWEN_VL_API_URL,
            api_key=settings.QWEN_VL_API_KEY,
        )

    async def call(self, image_url: str, prompt: str | None = None) -> dict:
        if not self.api_url or not self.api_key:
            return {"description": "", "objects": [], "scene": "", "colors": [], "text_in_image": "", "mood": ""}
        default_prompt = "请详细描述这张图片的内容，包括：场景、物体、颜色、文字、氛围。"
        return await self._request("POST", "/services/aigc/multimodal-generation/generation", {
            "model": "qwen-vl-plus",
            "input": {
                "messages": [
                    {"role": "user", "content": [
                        {"image": image_url},
                        {"text": prompt or default_prompt},
                    ]}
                ]
            },
        })

    async def understand_image(self, image_url: str, prompt: str | None = None) -> dict:
        result = await self.call(image_url, prompt)
        # Parse Qwen-VL response into structured format
        output = result.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "description": output if isinstance(output, str) else str(output),
            "objects": [],
            "scene": "",
            "colors": [],
            "text_in_image": "",
            "mood": "",
        }
