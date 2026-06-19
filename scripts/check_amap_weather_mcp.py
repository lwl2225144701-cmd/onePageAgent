from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "onepage_backend"
DEFAULT_MCP_URL = "http://127.0.0.1:8001/mcp"


try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env", override=False)
    load_dotenv(ROOT / ".env", override=False)
except Exception:
    pass


async def main() -> int:
    url = os.getenv("AMAP_WEATHER_MCP_URL", DEFAULT_MCP_URL).strip() or DEFAULT_MCP_URL
    timeout_seconds = int(os.getenv("MCP_TOOL_TIMEOUT_SECONDS", "10") or "10")
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": "MCP_SDK_UNAVAILABLE", "message": str(exc)}, ensure_ascii=False))
        return 2

    try:
        async with _open_streamable_http(streamablehttp_client, url, timeout_seconds) as streams:
            read_stream, write_stream = streams[0], streams[1]
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout_seconds)
                tools_result = await asyncio.wait_for(session.list_tools(), timeout=timeout_seconds)
                tools = [getattr(tool, "name", "") for tool in getattr(tools_result, "tools", [])]
                result = await asyncio.wait_for(
                    session.call_tool("journal_page_context", {"location": os.getenv("MCP_CHECK_LOCATION", "深圳市"), "timezone": "Asia/Shanghai"}),
                    timeout=timeout_seconds,
                )
                payload = _parse_tool_result(result)
                weather = payload.get("weather", {}) if isinstance(payload.get("weather"), dict) else {}
                location = payload.get("location", {}) if isinstance(payload.get("location"), dict) else {}
                dt = payload.get("datetime", {}) if isinstance(payload.get("datetime"), dict) else {}
                print(json.dumps(
                    {
                        "ok": bool(payload.get("ok")),
                        "url": url,
                        "tools": tools,
                        "date": dt.get("date"),
                        "city": location.get("city"),
                        "weather": weather.get("text"),
                        "weather_icon": weather.get("icon"),
                    },
                    ensure_ascii=False,
                ))
                return 0 if payload.get("ok") else 1
    except Exception as exc:
        print(json.dumps(
            {
                "ok": False,
                "url": url,
                "error_type": _classify_error(exc),
                "message": _exception_text(exc),
            },
            ensure_ascii=False,
        ))
        return 1


@asynccontextmanager
async def _open_streamable_http(streamablehttp_client, url: str, timeout_seconds: int):
    try:
        context = streamablehttp_client(url, timeout=timedelta(seconds=timeout_seconds))
    except TypeError:
        context = streamablehttp_client(url)
    async with context as streams:
        yield streams


def _parse_tool_result(result: Any) -> dict:
    if hasattr(result, "structuredContent") and getattr(result, "structuredContent"):
        return getattr(result, "structuredContent")
    if hasattr(result, "structured_content") and getattr(result, "structured_content"):
        return getattr(result, "structured_content")
    content = getattr(result, "content", None)
    if isinstance(content, list):
        for item in content:
            text = getattr(item, "text", None)
            if text is None and isinstance(item, dict):
                text = item.get("text")
            if text:
                return json.loads(text)
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        dumped = result.model_dump()
        return dumped if isinstance(dumped, dict) else {"result": dumped}
    return {"result": result}


def _classify_error(exc: BaseException) -> str:
    text = _exception_text(exc).lower()
    if "404" in text or "not found" in text:
        return "HTTP_404"
    if "connection refused" in text or "connect call failed" in text or "all connection attempts failed" in text:
        return "CONNECTION_REFUSED"
    if "timeout" in text or isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "TIMEOUT"
    if "invalid" in text:
        return "INVALID_MCP_RESPONSE"
    return exc.__class__.__name__ or "MCP_CHECK_FAILED"


def _exception_text(exc: BaseException) -> str:
    parts = [exc.__class__.__name__, str(exc)]
    if isinstance(exc, BaseExceptionGroup):
        parts.extend(_exception_text(item) for item in exc.exceptions)
    if exc.__cause__ is not None:
        parts.append(_exception_text(exc.__cause__))
    if exc.__context__ is not None:
        parts.append(_exception_text(exc.__context__))
    return " | ".join(part for part in parts if part)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
