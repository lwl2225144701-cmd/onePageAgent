import json

import httpx
import redis.asyncio as aioredis
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

UNKNOWN_WEATHER = {
    "province": "",
    "city": "",
    "district": "",
    "location": "",
    "adcode": "",
    "weather": "unknown",
    "temperature": None,
    "humidity": None,
    "wind_direction": "",
    "wind_power": "",
    "report_time": "",
    "icon_key": "unknown",
    "source": "unavailable",
}


class WeatherLookupError(RuntimeError):
    pass


class WeatherService:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def get_weather(self, lat: float, lng: float) -> dict:
        cache_key = f"weather:amap:{lat:.4f}:{lng:.4f}"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        logger.info("WEATHER_LOOKUP_START", lat=lat, lng=lng)
        location = None
        try:
            if not settings.AMAP_WEB_SERVICE_KEY:
                raise WeatherLookupError("AMAP_WEB_SERVICE_KEY is not configured")

            async with httpx.AsyncClient(timeout=8) as client:
                location = await self._reverse_geocode(client, lat=lat, lng=lng)
                weather = await self._get_live_weather(client, location=location)

            await self._cache(cache_key, weather, settings.WEATHER_CACHE_TTL)
            return weather
        except Exception as exc:
            logger.warning(
                "WEATHER_LOOKUP_FAILED",
                error_type=type(exc).__name__,
                error=str(exc),
                lat=lat,
                lng=lng,
            )
            failed = {
                **UNKNOWN_WEATHER,
                **(
                    {
                        **location,
                        "location": " ".join(part for part in (location["city"], location["district"]) if part),
                    }
                    if location
                    else {}
                ),
                "error_type": type(exc).__name__,
                "message": "天气暂不可用",
            }
            failure_ttl = max(5, min(30, settings.WEATHER_CACHE_TTL // 20))
            await self._cache(cache_key, failed, failure_ttl)
            return failed

    async def _reverse_geocode(self, client: httpx.AsyncClient, *, lat: float, lng: float) -> dict:
        response = await client.get(
            settings.AMAP_REVERSE_GEOCODE_URL,
            params={
                "key": settings.AMAP_WEB_SERVICE_KEY,
                "location": f"{lng},{lat}",
                "extensions": "base",
                "output": "JSON",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("status")) != "1":
            raise WeatherLookupError(str(payload.get("info") or "Amap reverse geocode failed"))

        component = payload.get("regeocode", {}).get("addressComponent", {})
        province = _text(component.get("province"))
        city = _text(component.get("city")) or province
        district = _text(component.get("district"))
        adcode = _text(component.get("adcode"))
        if not adcode:
            raise WeatherLookupError("Amap reverse geocode returned no adcode")

        logger.info("AMAP_REVERSE_GEOCODE_DONE", city=city, district=district, adcode=adcode)
        return {"province": province, "city": city, "district": district, "adcode": adcode}

    async def _get_live_weather(self, client: httpx.AsyncClient, *, location: dict) -> dict:
        response = await client.get(
            settings.AMAP_WEATHER_URL,
            params={
                "key": settings.AMAP_WEB_SERVICE_KEY,
                "city": location["adcode"],
                "extensions": "base",
                "output": "JSON",
            },
        )
        response.raise_for_status()
        payload = response.json()
        lives = payload.get("lives") if str(payload.get("status")) == "1" else None
        if not isinstance(lives, list) or not lives:
            raise WeatherLookupError(str(payload.get("info") or "Amap weather returned no live data"))

        live = lives[0]
        city = location["city"] or _text(live.get("city"))
        weather_text = _text(live.get("weather"))
        result = {
            "province": location["province"] or _text(live.get("province")),
            "city": city,
            "district": location["district"],
            "location": " ".join(dict.fromkeys(part for part in (city, location["district"]) if part)),
            "adcode": location["adcode"] or _text(live.get("adcode")),
            "weather": weather_text or "unknown",
            "temperature": _number(live.get("temperature")),
            "humidity": _number(live.get("humidity")),
            "wind_direction": _text(live.get("winddirection")),
            "wind_power": _text(live.get("windpower")),
            "report_time": _text(live.get("reporttime")),
            "icon_key": weather_icon_key(weather_text),
            "source": "amap",
        }
        logger.info(
            "AMAP_WEATHER_DONE",
            city=result["city"],
            weather=result["weather"],
            temperature=result["temperature"],
        )
        return result

    async def _get_cached(self, key: str) -> dict | None:
        try:
            value = await self.redis.get(key)
        except Exception as exc:
            logger.warning("weather_cache_read_failed", error=str(exc))
            return None
        return json.loads(value) if value else None

    async def _cache(self, key: str, data: dict, ttl: int) -> None:
        try:
            await self.redis.setex(key, ttl, json.dumps(data, ensure_ascii=False))
        except Exception as exc:
            logger.warning("weather_cache_write_failed", error=str(exc))


def weather_icon_key(weather: str) -> str:
    value = str(weather or "").strip()
    if not value:
        return "unknown"
    if "雷" in value:
        return "thunderstorm"
    if "雨夹雪" in value or "冻雨" in value:
        return "sleet"
    if "雪" in value:
        return "snow"
    if "雨" in value:
        return "rain"
    if any(term in value for term in ("雾", "霾")):
        return "fog"
    if any(term in value for term in ("沙", "尘")):
        return "dust"
    if "风" in value:
        return "wind"
    if "阴" in value:
        return "overcast"
    if "多云" in value:
        return "cloudy"
    if "晴" in value:
        return "sunny"
    return "unknown"


def _text(value: object) -> str:
    if isinstance(value, list):
        return _text(value[0]) if value else ""
    return str(value or "").strip()


def _number(value: object) -> int | float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number
