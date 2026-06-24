from datetime import datetime as real_datetime

import pytest

from app.ai import mcp_client


def _journal_context(*, date="2026-06-13", weather="阴", icon="☁️", icon_key="overcast", weather_success=True):
    return {
        "ok": True,
        "tool_success": True,
        "weather_success": weather_success,
        "datetime": {
            "date": date,
            "time": "21:24",
            "weekday": "星期六",
            "timezone": "Asia/Shanghai",
        },
        "location": {"city": "深圳市", "location_source": "user_selected"},
        "weather": {"text": weather if weather_success else None, "icon": icon if weather_success else None, "icon_key": icon_key},
        "journal_header": {
            "date_text": date,
            "weather_text": weather if weather_success else None,
            "weather_icon": icon if weather_success else None,
        },
        "semantic_tags": ["阴天"],
        "recommended_material_tags": ["云朵"],
    }


@pytest.mark.asyncio
async def test_generation_input_prefetches_mcp_context_before_dispatch(monkeypatch):
    captured = {}

    async def fake_context(location=None, timezone="Asia/Shanghai", *, task_id=None):
        captured.update({"location": location, "timezone": timezone, "task_id": task_id})
        context = _journal_context(weather="阵雨", icon="🌧️", icon_key="rain")
        context["location"].update({"district": "南山区", "city": "深圳市"})
        return context

    monkeypatch.setattr(mcp_client, "get_journal_page_context", fake_context)

    result = await mcp_client.prepare_generation_input(
        {"text": "今天去散步", "district": "南山区", "mood": "平静"},
        task_id="t-prefetch",
    )

    assert captured == {"location": "南山区", "timezone": "Asia/Shanghai", "task_id": "t-prefetch"}
    assert result["journal_context"]["weather"]["text"] == "阵雨"
    assert result["weather"]["icon"] == "🌧️"
    assert result["location"] == "南山区"
    assert result["page_date"] == "2026-06-13"


def test_orchestrator_reuses_request_environment_without_mcp(monkeypatch):
    async def forbidden_mcp_call(*args, **kwargs):
        raise AssertionError("generation pipeline must not call MCP")

    monkeypatch.setattr(mcp_client, "call_mcp_tool", forbidden_mcp_call)
    result = mcp_client.journal_context_from_input(
        {
            "environment_context": {
                "date": "2026-06-20",
                "time": "14:35",
                "weekday": "周六",
                "timezone": "Asia/Shanghai",
                "province": "广东省",
                "city": "深圳市",
                "district": "福田区",
                "location": "深圳市 福田区",
                "adcode": "440304",
                "weather": "多云",
                "temperature": 29,
                "humidity": 70,
                "icon_key": "cloudy",
                "report_time": "2026-06-20 14:30:00",
                "source": "amap",
            }
        },
        task_id="t-reuse",
    )

    assert result["source"] == "request_environment"
    assert result["journal_header"]["weather_text"] == "多云"
    assert result["journal_header"]["date_text"] == "2026.06.20 周六"
    assert result["location"]["district"] == "福田区"
    assert result["weather"]["temperature_celsius"] == 29


def test_missing_environment_uses_local_fallback_without_mcp(monkeypatch):
    async def forbidden_mcp_call(*args, **kwargs):
        raise AssertionError("legacy fallback must not call MCP")

    monkeypatch.setattr(mcp_client, "call_mcp_tool", forbidden_mcp_call)

    result = mcp_client.journal_context_from_input(
        {
            "location": "深圳市",
            "weather": {"weather": "多云", "icon": "⛅", "temperature": 27},
        },
        task_id="t-local-fallback",
    )

    assert result["weather_status"] == "success"
    assert result["weather_source"] == "request_payload"
    assert result["journal_header"]["weather_text"] == "多云"


def test_system_datetime_context_uses_frozen_current_date(monkeypatch):
    class FakeDatetime:
        @classmethod
        def now(cls, tz):
            return real_datetime(2026, 6, 13, 21, 24, tzinfo=tz)

    monkeypatch.setattr(mcp_client, "datetime", FakeDatetime)

    result = mcp_client.build_system_datetime_context("Asia/Shanghai")

    assert result["date"] == "2026-06-13"
    assert result["date"] != "2024-06-01"
    assert result["weekday"] == "星期六"


@pytest.mark.asyncio
async def test_mcp_unavailable_returns_system_date_without_weather(monkeypatch):
    class FakeDatetime:
        @classmethod
        def now(cls, tz):
            return real_datetime(2026, 6, 13, 21, 24, tzinfo=tz)

    async def failed_tool(*args, **kwargs):
        return {
            "source": "mcp",
            "ok": False,
            "type": "mcp_tool_result",
            "tool_name": "journal_page_context",
            "error_type": "MCP_SERVER_UNAVAILABLE",
            "message": "connection refused",
        }

    monkeypatch.setattr(mcp_client, "datetime", FakeDatetime)
    monkeypatch.setattr(mcp_client, "call_mcp_tool", failed_tool)

    context = await mcp_client.get_journal_page_context(location="深圳市", task_id="t-mcp-down")

    assert context["datetime"]["date"] == "2026-06-13"
    assert context["weather_success"] is False
    assert context["journal_header"]["weather_text"] is None
    assert context["error"]["error_type"] == "MCP_SERVER_UNAVAILABLE"


@pytest.mark.asyncio
async def test_invalid_location_auto_detects_before_weather_context(monkeypatch):
    calls = []

    async def fake_tool(tool_name, arguments=None, *, task_id=None):
        calls.append((tool_name, arguments or {}))
        if tool_name == "amap_get_current_location":
            return {
                "source": "amap",
                "ok": True,
                "type": "current_location",
                "province": "广东省",
                "city": "深圳市",
                "adcode": "440300",
            }
        if tool_name == "journal_page_context":
            assert arguments["location"] == "深圳市"
            return _journal_context(weather="阵雨", icon="🌧️", icon_key="rain")
        raise AssertionError(f"unexpected tool: {tool_name}")

    monkeypatch.setattr(mcp_client, "call_mcp_tool", fake_tool)

    context = await mcp_client.get_journal_page_context(location="未知", task_id="t-auto-location")

    assert calls[0][0] == "amap_get_current_location"
    assert calls[1] == ("journal_page_context", {"timezone": "Asia/Shanghai", "location": "深圳市"})
    assert context["location"]["location_source"] == "amap_auto_location"
    assert context["weather_status"] == "success"
    assert context["journal_header"]["weather_text"] == "阵雨"
