import json

import httpx
import redis.asyncio as aioredis

from app.config import settings

FALLBACK_WEATHER = {"weather": "unknown", "temperature": None, "location": "未知"}


class WeatherService:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def get_weather(self, lat: float, lng: float) -> dict:
        cache_key = f"weather:{lat:.2f}:{lng:.2f}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        if not settings.WEATHER_API_URL or not settings.WEATHER_API_KEY:
            await self._cache(cache_key, FALLBACK_WEATHER)
            return FALLBACK_WEATHER

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    settings.WEATHER_API_URL,
                    params={"lat": lat, "lng": lng, "key": settings.WEATHER_API_KEY},
                )
                resp.raise_for_status()
                data = resp.json()
                weather = self._parse_response(data)
                await self._cache(cache_key, weather)
                return weather
        except Exception:
            await self._cache(cache_key, FALLBACK_WEATHER)
            return FALLBACK_WEATHER

    async def _cache(self, key: str, data: dict):
        await self.redis.setex(key, settings.WEATHER_CACHE_TTL, json.dumps(data, ensure_ascii=False))

    def _parse_response(self, data: dict) -> dict:
        # Generic parser; override per actual API used (e.g., QWeather, Caiyun)
        return {
            "weather": str(data.get("weather", data.get("text", "unknown"))),
            "temperature": data.get("temperature", data.get("temp")),
            "location": str(data.get("location", data.get("city", "未知"))),
            "humidity": data.get("humidity"),
            "icon_url": data.get("icon_url"),
        }
