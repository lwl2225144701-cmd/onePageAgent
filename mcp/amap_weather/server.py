from __future__ import annotations

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP


load_dotenv(Path(__file__).with_name(".env"))
logging.getLogger("httpx").setLevel(logging.WARNING)

MCP_HOST = os.getenv("MCP_HOST") or os.getenv("MCP_HTTP_HOST") or "127.0.0.1"
MCP_PORT = int(os.getenv("MCP_PORT") or os.getenv("MCP_HTTP_PORT") or "8001")
MCP_PATH = os.getenv("MCP_PATH", "/mcp").strip() or "/mcp"
if not MCP_PATH.startswith("/"):
    MCP_PATH = f"/{MCP_PATH}"
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http").strip().lower()

mcp = FastMCP(
    "amap-weather-mcp",
    host=MCP_HOST,
    port=MCP_PORT,
    streamable_http_path=MCP_PATH,
)

AMAP_BASE_URL = "https://restapi.amap.com/v3"
AMAP_TIMEOUT_SECONDS = 8.0
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Shanghai")
WEEKDAYS_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def _amap_key() -> str:
    return os.getenv("AMAP_WEB_SERVICE_KEY", "").strip()


def _error(source: str, result_type: str, error_type: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "source": source,
        "ok": False,
        "type": result_type,
        "error_type": error_type,
        "message": message,
        **{key: value for key, value in extra.items() if value is not None},
    }


def _require_amap_key(result_type: str) -> dict[str, Any] | None:
    if _amap_key():
        return None
    return _error(
        "amap",
        result_type,
        "MISSING_AMAP_KEY",
        "缺少 AMAP_WEB_SERVICE_KEY，请先配置高德 Web 服务 Key。",
    )


def _amap_get(path: str, params: dict[str, Any], result_type: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    missing_key = _require_amap_key(result_type)
    if missing_key:
        return None, missing_key

    request_params = {"key": _amap_key(), "output": "JSON", **params}
    try:
        response = httpx.get(f"{AMAP_BASE_URL}{path}", params=request_params, timeout=AMAP_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.TimeoutException:
        return None, _error("amap", result_type, "AMAP_HTTP_TIMEOUT", "请求高德接口超时，请稍后重试。")
    except httpx.HTTPError as exc:
        return None, _error("amap", result_type, "AMAP_HTTP_ERROR", f"请求高德接口失败：{exc}")

    try:
        data = response.json()
    except ValueError:
        return None, _error("amap", result_type, "INVALID_RESPONSE", "高德接口返回了无法解析的 JSON。")

    if str(data.get("status")) != "1":
        return None, _error(
            "amap",
            result_type,
            "AMAP_API_ERROR",
            str(data.get("info") or "高德接口返回错误。"),
            info=data.get("info"),
            infocode=data.get("infocode"),
        )
    return data, None


def _clean_amap_value(value: Any) -> str:
    if isinstance(value, list):
        return ""
    return str(value or "").strip()


def _first_district(data: dict[str, Any]) -> dict[str, Any] | None:
    districts = data.get("districts")
    if not isinstance(districts, list):
        return None
    for item in districts:
        if not isinstance(item, dict):
            continue
        adcode = _clean_amap_value(item.get("adcode"))
        name = _clean_amap_value(item.get("name"))
        if adcode and name:
            return item
    return None


def _location_query_candidates(location: str) -> list[str]:
    raw = " ".join(str(location or "").strip().split())
    if not raw:
        return []

    candidates: list[str] = []

    def add(value: str) -> None:
        item = str(value or "").strip()
        if item and item not in candidates:
            candidates.append(item)

    add(raw)
    compact = raw.replace(" ", "")
    add(compact)

    parent_city = _parent_city_candidate(raw)
    if parent_city:
        add(parent_city)

    spaced = raw
    for separator in ("，", ",", "、", "/", "|"):
        spaced = spaced.replace(separator, " ")
    parts = [part.strip() for part in spaced.split() if part.strip()]
    if len(parts) > 1:
        add(parts[-1])
        add(parts[0])

    if "市" in compact:
        city_index = compact.rfind("市")
        add(compact[city_index + 1 :])
        add(compact[: city_index + 1])
    if "省" in compact:
        province_index = compact.rfind("省")
        add(compact[province_index + 1 :])

    return candidates


def _parent_city_candidate(location: str) -> str | None:
    raw = " ".join(str(location or "").strip().split())
    if not raw:
        return None
    parts = [part.strip() for part in raw.replace("，", " ").replace(",", " ").split() if part.strip()]
    for part in parts:
        if part.endswith("市"):
            return part

    compact = raw.replace(" ", "")
    if "市" not in compact:
        return None
    province_index = compact.rfind("省", 0, compact.rfind("市"))
    city_start = province_index + 1 if province_index >= 0 else 0
    city_end = compact.rfind("市") + 1
    city = compact[city_start:city_end].strip()
    return city or None


def map_weather_icon(weather: str) -> dict[str, str]:
    text = str(weather or "")
    if any(token in text for token in ("雷阵雨", "雷雨")):
        return {"icon": "⛈️", "icon_key": "thunderstorm"}
    if any(token in text for token in ("雪", "小雪", "中雪", "大雪", "暴雪")):
        return {"icon": "❄️", "icon_key": "snow"}
    if any(token in text for token in ("雨", "小雨", "中雨", "大雨", "暴雨", "阵雨")):
        return {"icon": "🌧️", "icon_key": "rain"}
    if any(token in text for token in ("雾", "霾", "浮尘", "扬沙", "沙尘暴")):
        return {"icon": "🌫️", "icon_key": "fog"}
    if "风" in text:
        return {"icon": "💨", "icon_key": "wind"}
    if any(token in text for token in ("少云", "晴间多云")):
        return {"icon": "🌤️", "icon_key": "partly_sunny"}
    if "多云" in text:
        return {"icon": "⛅", "icon_key": "cloudy_sunny"}
    if "阴" in text:
        return {"icon": "☁️", "icon_key": "overcast"}
    if "晴" in text:
        return {"icon": "☀️", "icon_key": "sunny"}
    return {"icon": "🌈", "icon_key": "unknown"}


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def build_journal_weather_context(weather_text: str, temperature_celsius: str | None = None) -> dict[str, list[str]]:
    text = str(weather_text or "")
    icon_key = map_weather_icon(text)["icon_key"]
    semantic_tags: list[str]
    mood_tags: list[str]
    material_tags: list[str]

    if icon_key == "sunny":
        semantic_tags = ["晴天", "阳光", "明亮"]
        mood_tags = ["清爽", "元气", "轻快"]
        material_tags = ["太阳", "蓝天", "光斑", "暖色贴纸"]
    elif icon_key in {"partly_sunny", "cloudy_sunny"}:
        semantic_tags = ["多云", "柔和", "天空"]
        mood_tags = ["松弛", "日常", "轻柔"]
        material_tags = ["云朵", "浅蓝背景", "纸张纹理"]
    elif icon_key == "overcast":
        semantic_tags = ["阴天", "低饱和", "安静"]
        mood_tags = ["平静", "松弛", "治愈"]
        material_tags = ["灰蓝背景", "云朵", "留白纸张"]
    elif icon_key == "thunderstorm":
        semantic_tags = ["雷雨", "强天气", "湿润"]
        mood_tags = ["戏剧感", "室内感", "安静"]
        material_tags = ["闪电", "雨滴", "深色背景", "窗户"]
    elif icon_key == "rain":
        semantic_tags = ["雨天", "潮湿", "降雨"]
        mood_tags = ["治愈", "安静", "室内感"]
        material_tags = ["雨滴", "伞", "窗户", "蓝灰色背景"]
    elif icon_key == "snow":
        semantic_tags = ["雪天", "寒冷", "冬日"]
        mood_tags = ["安静", "纯净", "温暖对比"]
        material_tags = ["雪花", "围巾", "热饮", "白色纹理"]
    elif icon_key == "fog":
        semantic_tags = ["雾天", "朦胧", "低能见度"]
        mood_tags = ["安静", "模糊感", "低饱和"]
        material_tags = ["雾气", "灰色背景", "朦胧纹理"]
    else:
        semantic_tags = ["天气", "日常"]
        mood_tags = ["记录", "自然"]
        material_tags = ["纸张纹理", "日常贴纸"]

    try:
        temperature = float(str(temperature_celsius).strip()) if temperature_celsius is not None else None
    except (TypeError, ValueError):
        temperature = None

    if temperature is not None and temperature >= 30:
        semantic_tags.append("炎热")
        mood_tags.append("夏日感")
        material_tags.extend(["冰饮", "水果", "清凉色背景"])
    if temperature is not None and temperature <= 10:
        semantic_tags.append("寒冷")
        mood_tags.extend(["温暖", "安静"])
        material_tags.extend(["热饮", "围巾", "暖色纸张"])

    return {
        "semantic_tags": _dedupe(semantic_tags),
        "mood_tags": _dedupe(mood_tags),
        "recommended_material_tags": _dedupe(material_tags),
    }


@mcp.tool()
def amap_get_current_location() -> dict[str, Any]:
    data, err = _amap_get("/ip", {}, "current_location")
    if err:
        return err

    province = _clean_amap_value(data.get("province"))
    city = _clean_amap_value(data.get("city"))
    adcode = _clean_amap_value(data.get("adcode"))
    rectangle = _clean_amap_value(data.get("rectangle"))
    if not city or not adcode:
        return _error(
            "amap",
            "current_location",
            "LOCATION_RESOLVE_FAILED",
            "无法通过 IP 定位获取城市，请用户手动提供城市名称。",
            province=province or None,
            city=city or None,
            adcode=adcode or None,
        )

    return {
        "source": "amap",
        "ok": True,
        "type": "current_location",
        "province": province,
        "city": city,
        "adcode": adcode,
        "rectangle": rectangle,
        "location_source": "amap_ip",
    }


@mcp.tool()
def amap_resolve_district(location: str) -> dict[str, Any]:
    input_location = str(location or "").strip()
    if not input_location:
        return _error(
            "amap",
            "district_resolve",
            "DISTRICT_NOT_FOUND",
            "未找到对应行政区，请输入更明确的城市或区县名称，例如 深圳市、广州市天河区。",
            input_location=input_location,
        )

    attempted_locations: list[str] = []
    last_err: dict[str, Any] | None = None
    for query_location in _location_query_candidates(input_location):
        attempted_locations.append(query_location)
        data, err = _amap_get(
            "/config/district",
            {"keywords": query_location, "subdistrict": 0, "extensions": "base"},
            "district_resolve",
        )
        if err:
            last_err = err
            continue

        district = _first_district(data or {})
        if not district:
            continue

        return {
            "source": "amap",
            "ok": True,
            "type": "district_resolve",
            "input_location": input_location,
            "query_location": query_location,
            "resolved_location": {
                "name": _clean_amap_value(district.get("name")),
                "adcode": _clean_amap_value(district.get("adcode")),
                "citycode": _clean_amap_value(district.get("citycode")),
                "level": _clean_amap_value(district.get("level")),
                "center": _clean_amap_value(district.get("center")),
            },
        }

    if last_err:
        return {**last_err, "input_location": input_location, "attempted_locations": attempted_locations}

    return _error(
        "amap",
        "district_resolve",
        "DISTRICT_NOT_FOUND",
        "未找到对应行政区，请输入更明确的城市或区县名称，例如 深圳市、广州市天河区。",
        input_location=input_location,
        attempted_locations=attempted_locations,
    )


@mcp.tool()
def journal_get_current_datetime(timezone: str | None = None) -> dict[str, Any]:
    tz_name = str(timezone or DEFAULT_TIMEZONE or "Asia/Shanghai").strip()
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return _error("system", "current_datetime", "INVALID_RESPONSE", f"无效时区：{tz_name}")

    now = datetime.now(tz)
    return {
        "source": "system",
        "ok": True,
        "type": "current_datetime",
        "timezone": tz_name,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "weekday": WEEKDAYS_ZH[now.weekday()],
        "iso_datetime": now.isoformat(timespec="seconds"),
    }


@mcp.tool()
def amap_current_weather(location: str | None = None) -> dict[str, Any]:
    input_location = str(location or "").strip()
    if input_location:
        resolved = amap_resolve_district(input_location)
        if not resolved.get("ok"):
            return {
                **resolved,
                "type": "current_weather",
                "input_location": input_location,
            }
        resolved_location = resolved["resolved_location"]
        adcode = resolved_location["adcode"]
        location_source = "amap_district"
    else:
        current_location = amap_get_current_location()
        if not current_location.get("ok"):
            return {**current_location, "type": "current_weather", "input_location": input_location or None}
        resolved_location = {
            "name": current_location.get("city"),
            "adcode": current_location.get("adcode"),
            "level": "city",
        }
        adcode = str(current_location.get("adcode") or "")
        location_source = "amap_ip"

    data, err = _amap_get(
        "/weather/weatherInfo",
        {"city": adcode, "extensions": "base"},
        "current_weather",
    )
    if err:
        parent_city = _parent_city_candidate(input_location)
        if parent_city and parent_city != input_location:
            parent_weather = amap_current_weather(parent_city)
            if parent_weather.get("ok"):
                return {
                    **parent_weather,
                    "input_location": input_location or None,
                    "resolved_location": resolved_location,
                    "location_source": "amap_district_parent_city",
                    "weather_location_fallback": parent_city,
                }
        return {
            **err,
            "input_location": input_location or None,
            "resolved_location": resolved_location,
        }

    lives = data.get("lives")
    if not isinstance(lives, list) or not lives:
        parent_city = _parent_city_candidate(input_location)
        if parent_city and parent_city != input_location:
            parent_weather = amap_current_weather(parent_city)
            if parent_weather.get("ok"):
                return {
                    **parent_weather,
                    "input_location": input_location or None,
                    "resolved_location": resolved_location,
                    "location_source": "amap_district_parent_city",
                    "weather_location_fallback": parent_city,
                }
        return _error(
            "amap",
            "current_weather",
            "INVALID_RESPONSE",
            "高德天气接口未返回实时天气数据。",
            input_location=input_location or None,
            resolved_location=resolved_location,
        )

    live = lives[0]
    weather_text = _clean_amap_value(live.get("weather"))
    icon = map_weather_icon(weather_text)
    return {
        "source": "amap",
        "ok": True,
        "type": "current_weather",
        "input_location": input_location or None,
        "resolved_location": resolved_location,
        "location_source": location_source,
        "province": _clean_amap_value(live.get("province")),
        "city": _clean_amap_value(live.get("city")),
        "adcode": _clean_amap_value(live.get("adcode")),
        "weather": weather_text,
        "weather_icon": icon["icon"],
        "weather_icon_key": icon["icon_key"],
        "temperature_celsius": _clean_amap_value(live.get("temperature")),
        "wind_direction": _clean_amap_value(live.get("winddirection")),
        "wind_power": _clean_amap_value(live.get("windpower")),
        "humidity": _clean_amap_value(live.get("humidity")),
        "report_time": _clean_amap_value(live.get("reporttime")),
    }


@mcp.tool()
def journal_page_context(location: str | None = None, timezone: str | None = None) -> dict[str, Any]:
    datetime_context = journal_get_current_datetime(timezone)
    if not datetime_context.get("ok"):
        return datetime_context

    input_location = str(location or "").strip()
    weather_context = amap_current_weather(input_location or None)
    if not weather_context.get("ok"):
        return {
            "source": "journal_mcp",
            "ok": False,
            "type": "journal_page_context",
            "error_type": weather_context.get("error_type", "UNKNOWN_ERROR"),
            "message": weather_context.get("message", "无法获取手帐页面上下文。"),
            "datetime": datetime_context,
            "weather_error": weather_context,
        }

    weather_tags = build_journal_weather_context(
        weather_context.get("weather", ""),
        weather_context.get("temperature_celsius"),
    )
    location_context = {
        "province": weather_context.get("province"),
        "city": weather_context.get("city"),
        "adcode": weather_context.get("adcode") or weather_context.get("resolved_location", {}).get("adcode"),
        "location_source": weather_context.get("location_source"),
    }
    return {
        "source": "journal_mcp",
        "ok": True,
        "type": "journal_page_context",
        "datetime": {
            "date": datetime_context["date"],
            "time": datetime_context["time"],
            "weekday": datetime_context["weekday"],
            "timezone": datetime_context["timezone"],
            "iso_datetime": datetime_context["iso_datetime"],
        },
        "location": location_context,
        "weather": {
            "text": weather_context.get("weather"),
            "icon": weather_context.get("weather_icon"),
            "icon_key": weather_context.get("weather_icon_key"),
            "temperature_celsius": weather_context.get("temperature_celsius"),
            "humidity": weather_context.get("humidity"),
            "wind_direction": weather_context.get("wind_direction"),
            "wind_power": weather_context.get("wind_power"),
            "report_time": weather_context.get("report_time"),
        },
        "journal_header": {
            "date_text": datetime_context["date"],
            "weather_text": weather_context.get("weather"),
            "weather_icon": weather_context.get("weather_icon"),
        },
        **weather_tags,
    }


if __name__ == "__main__":
    transport = MCP_TRANSPORT
    if transport == "http":
        print(
            "MCP_SERVER_START "
            f"transport=streamable-http host={MCP_HOST} port={MCP_PORT} path={MCP_PATH}",
            flush=True,
        )
        print(f"MCP_SERVER_READY url=http://{MCP_HOST}:{MCP_PORT}{MCP_PATH}", flush=True)
        mcp.run(transport="streamable-http")
    else:
        print("MCP_SERVER_START transport=stdio", flush=True)
        mcp.run(transport="stdio")
