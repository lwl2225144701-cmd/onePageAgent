from __future__ import annotations

import argparse
import asyncio
import json
from datetime import timedelta


async def main() -> None:
    parser = argparse.ArgumentParser(description="Check amap-weather MCP Streamable HTTP connectivity.")
    parser.add_argument("--url", default="http://127.0.0.1:8001/mcp")
    parser.add_argument("--location", default="")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    try:
        context = streamablehttp_client(args.url, timeout=timedelta(seconds=args.timeout))
    except TypeError:
        context = streamablehttp_client(args.url)

    async with context as streams:
        read_stream, write_stream = streams[0], streams[1]
        async with ClientSession(read_stream, write_stream) as session:
            await asyncio.wait_for(session.initialize(), timeout=args.timeout)
            tools_result = await asyncio.wait_for(session.list_tools(), timeout=args.timeout)
            tool_names = [tool.name for tool in getattr(tools_result, "tools", [])]
            print(json.dumps({"ok": True, "tools": tool_names}, ensure_ascii=False))
            if "journal_page_context" not in tool_names:
                raise SystemExit("journal_page_context not found")
            arguments = {"timezone": args.timezone}
            if args.location:
                arguments["location"] = args.location
            result = await asyncio.wait_for(session.call_tool("journal_page_context", arguments), timeout=args.timeout)
            payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
            print(json.dumps(payload, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())
