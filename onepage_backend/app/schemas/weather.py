from pydantic import BaseModel


class WeatherResponse(BaseModel):
    weather: str = "晴"
    temperature: float | None = None
    location: str = "未知"
    humidity: float | None = None
    icon_url: str | None = None
