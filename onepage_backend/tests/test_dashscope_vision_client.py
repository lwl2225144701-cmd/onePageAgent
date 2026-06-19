from __future__ import annotations

import pytest

from app.ai.gateway.dashscope_vision_client import (
    DashScopeVisionReviewClient,
    build_image_data_url,
    normalize_dashscope_vision_model,
    validate_data_url_size,
)


class _Delta:
    def __init__(self, content: str | None):
        self.content = content


class _Choice:
    def __init__(self, content: str | None):
        self.delta = _Delta(content)


class _Chunk:
    def __init__(self, content: str | None = None, usage: dict | None = None):
        self.choices = [_Choice(content)] if content is not None else []
        self.usage = usage


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class _FakeCompletions:
    def __init__(self):
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return _FakeStream(
            [
                _Chunk('{"items":['),
                _Chunk('{"label":"A01","decision":"keep"}]}'),
                _Chunk(usage={"prompt_tokens": 10, "completion_tokens": 8}),
            ]
        )


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self):
        self.completions = _FakeCompletions()
        self.chat = _FakeChat(self.completions)
        self.closed = False

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_dashscope_streaming_review_uses_data_url_and_text_only_modalities():
    fake = _FakeClient()
    client = DashScopeVisionReviewClient()
    client.api_key = "test-key"
    client._client = fake

    result = await client.review_contact_sheet(
        prompt="只输出 JSON",
        contact_sheet_data_url="data:image/jpeg;base64,abc123",
        task_id="t-stream",
    )

    kwargs = fake.completions.kwargs
    content = kwargs["messages"][0]["content"]
    assert content[0]["image_url"]["url"] == "data:image/jpeg;base64,abc123"
    assert "127.0.0.1" not in content[0]["image_url"]["url"]
    assert kwargs["stream"] is True
    assert kwargs["extra_body"]["modalities"] == ["text"]
    assert "audio" not in kwargs["extra_body"]
    assert result["content"] == '{"items":[{"label":"A01","decision":"keep"}]}'
    assert result["usage"]["prompt_tokens"] == 10


def test_dashscope_data_url_size_guard_counts_encoded_url_bytes():
    data_url = build_image_data_url(b"abc123", "image/jpeg")

    assert data_url.startswith("data:image/jpeg;base64,")
    assert validate_data_url_size(data_url, max_bytes=len(data_url.encode("utf-8"))) == len(data_url.encode("utf-8"))
    with pytest.raises(Exception, match="contact_sheet_data_url_too_large"):
        validate_data_url_size(data_url, max_bytes=10)


def test_dashscope_model_alias_maps_404_prone_flash_name_to_lightweight_default():
    assert normalize_dashscope_vision_model("qwen3.5-omni-flash") == "qwen3-omni-flash"
    assert normalize_dashscope_vision_model("qwen3.5-omni-plus") == "qwen3.5-omni-plus"
