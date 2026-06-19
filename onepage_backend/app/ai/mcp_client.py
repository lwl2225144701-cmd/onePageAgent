from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

DEFAULT_TIMEZONE = "Asia/Shanghai"
WEEKDAYS_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
INVALID_LOCATION_VALUES = {"", "未知", "未设置", "未选择", "unknown", "none", "null"}


async def call_mcp_tool(tool_name: str, arguments: dict | None = None, *, task_id: str | None = None) -> dict:
    """Call an MCP tool over Streamable HTTP and return a stable dict result.

    The SDK import stays inside this function so workers without MCP installed do
    not crash during module import. Connection and tool failures are returned as
    structured errors for the orchestrator to handle gracefully.
    """

    arguments = arguments or {}
    mcp_url = settings.AMAP_WEATHER_MCP_URL
    timeout_seconds = max(1, int(settings.MCP_TOOL_TIMEOUT_SECONDS or 10))
    safe_arguments = _redact_arguments(arguments)

    if settings.PIPELINE_DEBUG_TRACE:
        _log_line("MCP_CLIENT_CONNECT_START", task_id=task_id)
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except Exception as exc:
        result = _tool_error(
            tool_name=tool_name,
            error_type="MCP_CLIENT_UNAVAILABLE",
            message=f"MCP Python SDK is unavailable: {exc}",
        )
        _log_line("MCP_TOOL_CALL_FAILED", task_id=task_id, tool_name=tool_name, error_type=result["error_type"], error_message=result["message"])
        return result

    started = time.perf_counter()
    try:
        async with _open_streamable_http(streamablehttp_client, mcp_url, timeout_seconds) as streams:
            read_stream, write_stream = streams[0], streams[1]
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout_seconds)
                _log_line("MCP_CONNECT_OK", task_id=task_id)

                tools_result = await asyncio.wait_for(session.list_tools(), timeout=timeout_seconds)
                tool_names = {getattr(tool, "name", "") for tool in getattr(tools_result, "tools", [])}
                _log_line("MCP_TOOLS_READY", task_id=task_id, count=len(tool_names))
                if tool_names and tool_name not in tool_names:
                    raise ValueError(f"MCP tool not registered: {tool_name}")

                _log_line("MCP_TOOL_CALL_START", task_id=task_id, tool_name=tool_name, arguments=json.dumps(safe_arguments, ensure_ascii=False))
                call_result = await asyncio.wait_for(session.call_tool(tool_name, arguments), timeout=timeout_seconds)
                parsed = _parse_tool_result(call_result)
                ok = bool(parsed.get("ok", True)) if isinstance(parsed, dict) else True
                duration_ms = int((time.perf_counter() - started) * 1000)
                error_type = parsed.get("error_type") if isinstance(parsed, dict) and not ok else None
                error_message = str(parsed.get("message") or "")[:160] if isinstance(parsed, dict) and not ok else None
                _log_line(
                    "MCP_TOOL_CALL_DONE",
                    task_id=task_id,
                    tool_name=tool_name,
                    duration_ms=duration_ms,
                    ok=ok,
                    error_type=error_type,
                    error_message=error_message,
                )
                if isinstance(parsed, dict):
                    return parsed
                return {"source": "mcp", "ok": True, "type": "tool_result", "result": parsed}
    except Exception as exc:
        error_type = _classify_mcp_error(exc)
        result = _tool_error(tool_name=tool_name, error_type=error_type, message=str(exc))
        _log_line("MCP_TOOL_CALL_FAILED", task_id=task_id, tool_name=tool_name, error_type=error_type, error_message=str(exc)[:300])
        if error_type == "MCP_SERVER_UNAVAILABLE":
            _log_line("MCP_SERVER_UNAVAILABLE", task_id=task_id, mcp_url=mcp_url)
        return result


async def get_journal_page_context(
    location: str | None = None,
    timezone: str = DEFAULT_TIMEZONE,
    *,
    task_id: str | None = None,
) -> dict:
    clean_location = None if is_invalid_location(location) else str(location or "").strip()
    location_source = "browser_location" if clean_location else "unavailable"
    if clean_location is None:
        _log_line("LOCATION_AUTO_DETECT_START", task_id=task_id)
        auto_location = await call_mcp_tool("amap_get_current_location", {}, task_id=task_id)
        if auto_location.get("ok"):
            clean_location = _choose_location(auto_location)
            location_source = "amap_auto_location" if clean_location else "unavailable"
            _log_line(
                "LOCATION_AUTO_DETECT_OK",
                task_id=task_id,
                location=clean_location,
                city=auto_location.get("city"),
                adcode=auto_location.get("adcode"),
            )
        else:
            default_location = None if is_invalid_location(settings.DEFAULT_WEATHER_LOCATION) else settings.DEFAULT_WEATHER_LOCATION.strip()
            if default_location:
                clean_location = default_location
                location_source = "configured_default"
                _log_line("LOCATION_AUTO_DETECT_FAILED", task_id=task_id, reason=auto_location.get("error_type"), fallback="configured_default")
            else:
                _log_line("LOCATION_AUTO_DETECT_FAILED", task_id=task_id, reason=auto_location.get("error_type"), fallback="unavailable")

    if clean_location is None:
        datetime_context = await _get_datetime_context(timezone, task_id=task_id)
        context = build_fallback_journal_context(
            location=None,
            timezone=timezone,
            datetime_context=datetime_context,
            location_source="unavailable",
            error=_tool_error(
                tool_name="journal_page_context",
                error_type="LOCATION_UNAVAILABLE",
                message="Location unavailable; weather context skipped.",
            ),
        )
        _log_journal_context_ready(context, task_id=task_id)
        return context

    arguments = {
        "timezone": timezone or DEFAULT_TIMEZONE,
    }
    if clean_location:
        arguments["location"] = clean_location

    result = await call_mcp_tool("journal_page_context", arguments, task_id=task_id)
    if result.get("ok"):
        context = normalize_journal_context(result, location=clean_location, timezone=timezone, location_source=location_source)
    else:
        context = build_fallback_journal_context(location=clean_location, timezone=timezone, location_source=location_source, error=result)

    _log_journal_context_ready(context, task_id=task_id)
    return context


async def prepare_generation_input(input_json: dict, *, task_id: str) -> dict:
    """Resolve journal context before dispatching the AI orchestration task."""

    payload = dict(input_json) if isinstance(input_json, dict) else {}
    existing = payload.get("journal_context")
    if _has_prefetched_context(existing):
        _log_line("MCP_CONTEXT_PREFETCH_REUSED", task_id=task_id)
        return payload

    location = extract_location_hint(payload)
    timezone = str(payload.get("timezone") or DEFAULT_TIMEZONE)
    _log_line("MCP_CONTEXT_PREFETCH_START", task_id=task_id, location=location, timezone=timezone)
    context = await get_journal_page_context(location=location, timezone=timezone, task_id=task_id)
    payload["journal_context"] = context
    payload["page_date"] = str(context.get("journal_header", {}).get("date_text") or context.get("date") or "")

    location_context = context.get("location", {}) if isinstance(context.get("location"), dict) else {}
    resolved_location = _clean_text(
        location_context.get("district")
        or location_context.get("city")
        or location_context.get("input_location")
        or location
    )
    if resolved_location:
        payload["location"] = resolved_location
    for key in ("city", "district"):
        value = _clean_text(location_context.get(key))
        if value:
            payload[key] = value

    weather_context = context.get("weather", {}) if isinstance(context.get("weather"), dict) else {}
    if context.get("weather_success"):
        payload["weather"] = {
            **(payload.get("weather") if isinstance(payload.get("weather"), dict) else {}),
            "weather": weather_context.get("text"),
            "text": weather_context.get("text"),
            "icon": weather_context.get("icon"),
            "icon_key": weather_context.get("icon_key"),
            "temperature": weather_context.get("temperature_celsius"),
            "temperature_celsius": weather_context.get("temperature_celsius"),
            "location": resolved_location,
            "city": location_context.get("city"),
            "district": location_context.get("district"),
        }
    _log_line(
        "MCP_CONTEXT_PREFETCH_DONE",
        task_id=task_id,
        weather_status=context.get("weather_status"),
        location_status=context.get("location_status"),
        source=context.get("source"),
    )
    return payload


def journal_context_from_input(input_json: dict, *, task_id: str | None = None) -> dict:
    """Load the task-creation snapshot without making any MCP or network call."""

    payload = input_json if isinstance(input_json, dict) else {}
    context = payload.get("journal_context")
    if _has_prefetched_context(context):
        snapshot = dict(context)
        _log_line(
            "JOURNAL_CONTEXT_REUSED",
            task_id=task_id,
            source=snapshot.get("source"),
            weather_status=snapshot.get("weather_status"),
        )
        return snapshot

    timezone = str(payload.get("timezone") or DEFAULT_TIMEZONE)
    datetime_context = build_system_datetime_context(timezone)
    page_date = _clean_text(payload.get("page_date"))
    if page_date:
        datetime_context["date"] = page_date
    location = extract_location_hint(payload)
    snapshot = build_fallback_journal_context(
        location=location,
        timezone=timezone,
        datetime_context=datetime_context,
        location_source="request_payload" if location else "unavailable",
        error=_tool_error(
            tool_name="journal_page_context",
            error_type="PREFETCH_CONTEXT_MISSING",
            message="Generation input did not contain a prefetched journal context.",
        ),
    )
    _merge_legacy_weather(snapshot, payload.get("weather"))
    _log_line("JOURNAL_CONTEXT_LOCAL_FALLBACK", task_id=task_id, location=location, weather_status=snapshot.get("weather_status"))
    return snapshot


def extract_location_hint(input_json: dict) -> str | None:
    if not isinstance(input_json, dict):
        return None
    candidates: list[object] = [
        input_json.get("district"),
        input_json.get("city"),
        input_json.get("location"),
        input_json.get("location_name"),
    ]
    for key in ("frontend_location", "geo", "weather"):
        value = input_json.get(key)
        if isinstance(value, dict):
            candidates.extend([value.get("district"), value.get("city"), value.get("location"), value.get("name")])
    for value in candidates:
        if isinstance(value, str) and not is_invalid_location(value):
            return value.strip()
    return None


def _has_prefetched_context(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    datetime_context = value.get("datetime")
    return isinstance(datetime_context, dict) and bool(datetime_context.get("date"))


def _merge_legacy_weather(context: dict, value: object) -> None:
    if not isinstance(value, dict):
        return
    weather_text = _clean_text(value.get("weather") or value.get("text"))
    if not weather_text or weather_text.lower() in {"unknown", "none", "null"}:
        return
    icon = _clean_text(value.get("icon") or value.get("weather_icon"))
    icon_key = _clean_text(value.get("icon_key") or value.get("weather_icon_key"))
    temperature = value.get("temperature_celsius", value.get("temperature"))
    context["weather_success"] = True
    context["weather_status"] = "success"
    context["weather_source"] = "request_payload"
    context["weather_text"] = weather_text
    context["weather_icon"] = icon
    context["temperature"] = temperature
    context["weather"] = {
        **context.get("weather", {}),
        "text": weather_text,
        "icon": icon,
        "icon_key": icon_key or "unknown",
        "temperature_celsius": temperature,
    }
    context["journal_header"] = {
        **context.get("journal_header", {}),
        "weather_text": weather_text,
        "weather_icon": icon,
    }


def _log_journal_context_ready(context: dict, *, task_id: str | None = None) -> None:
    datetime_context = context.get("datetime", {}) if isinstance(context.get("datetime"), dict) else {}
    location_context = context.get("location", {}) if isinstance(context.get("location"), dict) else {}
    weather_context = context.get("weather", {}) if isinstance(context.get("weather"), dict) else {}
    _log_line(
        "JOURNAL_CONTEXT_READY",
        task_id=task_id,
        date=datetime_context.get("date"),
        timezone=datetime_context.get("timezone"),
        city=location_context.get("city"),
        weather=weather_context.get("text") or "unknown",
        weather_icon=weather_context.get("icon"),
        location_source=location_context.get("location_source"),
        weather_status=context.get("weather_status"),
    )


def normalize_journal_context(
    result: dict,
    *,
    location: str | None = None,
    timezone: str = DEFAULT_TIMEZONE,
    location_source: str | None = None,
) -> dict:
    """Normalize MCP output so downstream steps can rely on stable keys."""

    context = dict(result)
    datetime_context = context.get("datetime") if isinstance(context.get("datetime"), dict) else {}
    if not datetime_context.get("date"):
        datetime_context = build_system_datetime_context(timezone)
    context["datetime"] = datetime_context

    weather_context = context.get("weather") if isinstance(context.get("weather"), dict) else {}
    weather_text = _clean_text(weather_context.get("text") or weather_context.get("weather"))
    weather_icon = _clean_text(weather_context.get("icon") or weather_context.get("weather_icon"))
    weather_icon_key = _clean_text(weather_context.get("icon_key") or weather_context.get("weather_icon_key"))
    weather_success = bool(context.get("weather_success", context.get("ok") and weather_text))
    context["weather_success"] = weather_success
    context["weather_status"] = "success" if weather_success else "unavailable"
    context["tool_success"] = bool(context.get("ok"))
    context["weather"] = {
        **weather_context,
        "text": weather_text or None,
        "icon": weather_icon or None,
        "icon_key": weather_icon_key or None,
    }

    location_context = context.get("location") if isinstance(context.get("location"), dict) else {}
    if location_source:
        location_context["location_source"] = location_source
    elif location and not location_context.get("location_source"):
        location_context["location_source"] = "browser_location"
    elif not location_context.get("location_source"):
        location_context["location_source"] = "unavailable"
    if location and not location_context.get("input_location"):
        location_context["input_location"] = location
    context["location"] = location_context
    context["location_status"] = "success" if location_context.get("city") or location_context.get("input_location") else "unavailable"

    journal_header = context.get("journal_header") if isinstance(context.get("journal_header"), dict) else {}
    journal_header["date_text"] = _clean_text(journal_header.get("date_text")) or datetime_context["date"]
    journal_header["weather_text"] = weather_text if weather_success else None
    journal_header["weather_icon"] = weather_icon if weather_success else None
    context["journal_header"] = journal_header
    context["date"] = datetime_context.get("date")
    context["time"] = datetime_context.get("time")
    context["weekday"] = datetime_context.get("weekday")
    context["timezone"] = datetime_context.get("timezone")
    context["weather_source"] = "amap" if weather_success else None
    context["weather_text"] = weather_text if weather_success else None
    context["weather_icon"] = weather_icon if weather_success else None
    context["temperature"] = context["weather"].get("temperature_celsius")
    context.setdefault("semantic_tags", [])
    context.setdefault("mood_tags", [])
    context.setdefault("recommended_material_tags", [])
    context.setdefault("source", "journal_mcp")
    context["ok"] = True
    return context


def build_fallback_journal_context(
    *,
    location: str | None = None,
    timezone: str = DEFAULT_TIMEZONE,
    datetime_context: dict | None = None,
    location_source: str | None = None,
    error: dict | None = None,
) -> dict:
    datetime_context = datetime_context if isinstance(datetime_context, dict) and datetime_context.get("date") else build_system_datetime_context(timezone)
    error_type = str((error or {}).get("error_type") or "")
    weather_status = "unavailable" if error_type in {"", "LOCATION_UNAVAILABLE"} else "failed"
    return {
        "source": "orchestrator_fallback",
        "ok": True,
        "tool_success": False,
        "weather_success": False,
        "weather_status": weather_status,
        "location_status": "success" if location else "unavailable",
        "type": "journal_page_context",
        "datetime": datetime_context,
        "location": {
            "input_location": location,
            "city": location,
            "location_source": location_source or ("browser_location" if location else "unavailable"),
        },
        "weather": {
            "text": None,
            "icon": None,
            "icon_key": "unknown",
            "temperature_celsius": None,
            "humidity": None,
            "report_time": None,
        },
        "journal_header": {
            "date_text": datetime_context["date"],
            "weather_text": None,
            "weather_icon": None,
        },
        "semantic_tags": [],
        "mood_tags": [],
        "recommended_material_tags": [],
        "date": datetime_context.get("date"),
        "time": datetime_context.get("time"),
        "weekday": datetime_context.get("weekday"),
        "timezone": datetime_context.get("timezone"),
        "weather_source": None,
        "weather_text": None,
        "weather_icon": None,
        "temperature": None,
        "error": error or _tool_error(
            tool_name="journal_page_context",
            error_type="MCP_SERVER_UNAVAILABLE",
            message="MCP server unavailable; using system datetime only.",
        ),
    }


async def _get_datetime_context(timezone: str, *, task_id: str | None = None) -> dict:
    result = await call_mcp_tool("journal_get_current_datetime", {"timezone": timezone or DEFAULT_TIMEZONE}, task_id=task_id)
    if result.get("ok"):
        return {
            "source": result.get("source", "system"),
            "ok": True,
            "type": "current_datetime",
            "timezone": result.get("timezone") or timezone or DEFAULT_TIMEZONE,
            "date": result.get("date"),
            "time": result.get("time"),
            "weekday": result.get("weekday"),
            "iso_datetime": result.get("iso_datetime"),
        }
    return build_system_datetime_context(timezone)


def is_invalid_location(value: str | None) -> bool:
    if value is None:
        return True
    normalized = str(value or "").strip().lower()
    return normalized in INVALID_LOCATION_VALUES


def _choose_location(result: dict) -> str | None:
    for key in ("district", "city", "province", "location"):
        value = _clean_text(result.get(key))
        if value and not is_invalid_location(value):
            return value
    resolved = result.get("resolved_location") if isinstance(result.get("resolved_location"), dict) else {}
    return _clean_text(resolved.get("name")) or None


def build_system_datetime_context(timezone: str = DEFAULT_TIMEZONE) -> dict:
    tz_name = timezone or DEFAULT_TIMEZONE
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz_name = DEFAULT_TIMEZONE
        tz = ZoneInfo(DEFAULT_TIMEZONE)
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


@asynccontextmanager
async def _open_streamable_http(streamablehttp_client, mcp_url: str, timeout_seconds: int):
    try:
        context = streamablehttp_client(mcp_url, timeout=timedelta(seconds=timeout_seconds))
    except TypeError:
        context = streamablehttp_client(mcp_url)
    async with context as streams:
        yield streams


def _parse_tool_result(result: Any) -> Any:
    if isinstance(result, dict):
        return result
    if hasattr(result, "structuredContent"):
        structured = getattr(result, "structuredContent")
        if structured:
            return structured
    if hasattr(result, "structured_content"):
        structured = getattr(result, "structured_content")
        if structured:
            return structured
    content = getattr(result, "content", None)
    if isinstance(content, list):
        for item in content:
            text = getattr(item, "text", None)
            if text is None and isinstance(item, dict):
                text = item.get("text")
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"source": "mcp", "ok": True, "type": "tool_text", "text": text}
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result


def _tool_error(*, tool_name: str, error_type: str, message: str) -> dict:
    return {
        "source": "mcp",
        "ok": False,
        "type": "mcp_tool_result",
        "tool_name": tool_name,
        "error_type": error_type,
        "message": message,
    }


def _classify_mcp_error(exc: Exception) -> str:
    text = _exception_text(exc)
    if any(
        token in text
        for token in (
            "connection refused",
            "connect call failed",
            "all connection attempts failed",
            "timeout",
            "connecterror",
            "connect_error",
        )
    ):
        return "MCP_SERVER_UNAVAILABLE"
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "MCP_SERVER_UNAVAILABLE"
    if isinstance(exc, BaseExceptionGroup):
        return "MCP_SERVER_UNAVAILABLE"
    return exc.__class__.__name__ or "MCP_TOOL_ERROR"


def _exception_text(exc: BaseException) -> str:
    parts = [exc.__class__.__name__, str(exc)]
    if isinstance(exc, BaseExceptionGroup):
        for item in exc.exceptions:
            parts.append(_exception_text(item))
    if exc.__cause__ is not None:
        parts.append(_exception_text(exc.__cause__))
    if exc.__context__ is not None:
        parts.append(_exception_text(exc.__context__))
    return " ".join(parts).lower()


def _redact_arguments(arguments: dict) -> dict:
    safe: dict[str, Any] = {}
    for key, value in arguments.items():
        if "key" in str(key).lower() or "token" in str(key).lower() or "secret" in str(key).lower():
            safe[key] = "***"
        else:
            safe[key] = value
    return safe


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _log_line(event: str, **fields: Any) -> None:
    parts = [event]
    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    print(" ".join(parts), flush=True)
