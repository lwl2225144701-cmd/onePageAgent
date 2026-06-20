import json

import pytest

from app.services.weather_service import WeatherService, weather_icon_key


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.writes = []

    async def get(self, key):
        return self.values.get(key)

    async def setex(self, key, ttl, value):
        self.values[key] = value
        self.writes.append((key, ttl, json.loads(value)))


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, responses, calls):
        self.responses = iter(responses)
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, params):
        self.calls.append((url, params))
        return FakeResponse(next(self.responses))


@pytest.mark.asyncio
async def test_weather_lookup_uses_lng_lat_and_adcode(monkeypatch):
    calls = []
    responses = [
        {
            "status": "1",
            "regeocode": {
                "addressComponent": {
                    "province": "广东省",
                    "city": "深圳市",
                    "district": "福田区",
                    "adcode": "440304",
                }
            },
        },
        {
            "status": "1",
            "lives": [
                {
                    "province": "广东",
                    "city": "深圳市",
                    "adcode": "440300",
                    "weather": "多云",
                    "temperature": "29",
                    "humidity": "70",
                    "winddirection": "南",
                    "windpower": "≤3",
                    "reporttime": "2026-06-20 14:30:00",
                }
            ],
        },
    ]
    monkeypatch.setattr("app.services.weather_service.httpx.AsyncClient", lambda **kwargs: FakeClient(responses, calls))

    redis = FakeRedis()
    result = await WeatherService(redis).get_weather(22.5431, 114.0579)

    assert calls[0][1]["location"] == "114.0579,22.5431"
    assert calls[1][1]["city"] == "440304"
    assert result["location"] == "深圳市 福田区"
    assert result["weather"] == "多云"
    assert result["temperature"] == 29
    assert result["icon_key"] == "cloudy"
    assert result["source"] == "amap"


@pytest.mark.asyncio
async def test_weather_failure_returns_unknown_with_short_cache(monkeypatch):
    calls = []
    responses = [{"status": "0", "info": "INVALID_USER_KEY"}]
    monkeypatch.setattr("app.services.weather_service.httpx.AsyncClient", lambda **kwargs: FakeClient(responses, calls))

    redis = FakeRedis()
    result = await WeatherService(redis).get_weather(22.5431, 114.0579)

    assert result["weather"] == "unknown"
    assert result["temperature"] is None
    assert result["source"] == "unavailable"
    assert redis.writes[0][1] <= 30


@pytest.mark.parametrize(
    ("weather", "expected"),
    [("晴", "sunny"), ("多云", "cloudy"), ("雷阵雨", "thunderstorm"), ("雨夹雪", "sleet"), ("扬沙", "dust")],
)
def test_weather_icon_key(weather, expected):
    assert weather_icon_key(weather) == expected
