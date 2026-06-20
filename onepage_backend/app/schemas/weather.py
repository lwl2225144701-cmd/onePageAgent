from pydantic import BaseModel


class WeatherResponse(BaseModel):
    province: str = ""
    city: str = ""
    district: str = ""
    location: str = ""
    adcode: str = ""
    weather: str = "unknown"
    temperature: float | None = None
    humidity: float | None = None
    wind_direction: str = ""
    wind_power: str = ""
    report_time: str = ""
    icon_key: str = "unknown"
    source: str = "unavailable"
    error_type: str | None = None
    message: str | None = None
