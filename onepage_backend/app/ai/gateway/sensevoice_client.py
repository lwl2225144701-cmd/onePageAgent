from app.ai.gateway.base import BaseModelClient
from app.config import settings


class SenseVoiceClient(BaseModelClient):
    def __init__(self):
        super().__init__(
            api_url=settings.SENSEVOICE_API_URL,
            api_key=settings.SENSEVOICE_API_KEY,
        )

    async def call(self, audio_url: str, task: str = "recognize") -> dict:
        if not self.api_url or not self.api_key:
            return {"text": "", "emotion": "neutral", "emotion_confidence": 0.0}
        return await self._request("POST", "/v1/recognize", {"audio_url": audio_url, "task": task})

    async def recognize_speech(self, audio_url: str) -> str:
        result = await self.call(audio_url, "asr")
        return result.get("text", "")

    async def recognize_emotion(self, audio_url: str) -> dict:
        result = await self.call(audio_url, "emotion")
        return {
            "emotion": result.get("emotion", "neutral"),
            "confidence": result.get("confidence", 0.0),
        }
