import pytest

from app.ai.pipeline.llm_json import extract_message_content, parse_json_content, run_json_llm_step


def test_extract_message_content_supports_openai_shape():
    payload = {"choices": [{"message": {"content": "{\"ok\": true}"}}]}
    assert extract_message_content(payload) == "{\"ok\": true}"


def test_extract_message_content_supports_qwen_shape():
    payload = {"output": {"choices": [{"message": {"content": "{\"ok\": true}"}}]}}
    assert extract_message_content(payload) == "{\"ok\": true}"


def test_parse_json_content_returns_default_for_empty():
    default = {"fallback": True}
    assert parse_json_content("", default) == default


@pytest.mark.asyncio
async def test_run_json_llm_step_parses_json_and_closes_client():
    state = {"closed": False}

    class FakeClient:
        async def chat(self, **kwargs):
            return {"choices": [{"message": {"content": "{\"theme\": \"healing\"}"}}]}

        async def close(self):
            state["closed"] = True

    result = await run_json_llm_step(
        client_factory=FakeClient,
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="sys",
        temperature=0.1,
        response_format={"type": "json_object"},
        default={},
    )

    assert result == {"theme": "healing"}
    assert state["closed"] is True
