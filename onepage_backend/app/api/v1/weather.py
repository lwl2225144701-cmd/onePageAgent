from fastapi import APIRouter, Depends, Query
import redis.asyncio as aioredis

from app.api.deps import get_redis
from app.schemas.common import UnifiedResponse
from app.schemas.weather import WeatherResponse
from app.services.weather_service import WeatherService

router = APIRouter()


@router.get("", response_model=UnifiedResponse[WeatherResponse])
async def get_weather(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    redis: aioredis.Redis = Depends(get_redis),
):
    svc = WeatherService(redis)
    data = await svc.get_weather(lat, lng)
    return UnifiedResponse(data=WeatherResponse(**data))
