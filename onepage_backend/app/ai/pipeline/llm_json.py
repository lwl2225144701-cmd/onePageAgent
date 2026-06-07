import json
from collections.abc import Awaitable, Callable
from typing import Any


def extract_message_content(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""

    content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    if content:
        return str(content).strip()

    output_content = payload.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content", "")
    if output_content:
        return str(output_content).strip()

    return ""


def parse_json_content(content: str | dict[str, Any] | list[Any] | None, default: Any) -> Any:
    if content is None or content == "":
        return default
    if isinstance(content, (dict, list)):
        return content
    return json.loads(content)


async def run_json_llm_step(
    *,
    client_factory: Callable[[], Any],
    messages: list[dict[str, Any]],
    system_prompt: str | None,
    temperature: float,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
    default: Any,
) -> Any:
    client = client_factory()
    try:
        response = await client.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        content = extract_message_content(response)
        return parse_json_content(content, default)
    finally:
        close = getattr(client, "close", None)
        if close:
            result = close()
            if isinstance(result, Awaitable):
                await result
