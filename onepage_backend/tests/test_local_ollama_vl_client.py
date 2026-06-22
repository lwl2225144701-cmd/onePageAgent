from __future__ import annotations

import base64
import json

import httpx
import pytest

from app.ai.gateway.dashscope_vision_client import DashScopeVisionReviewClient
from app.ai.gateway.local_ollama_vl_client import LocalOllamaVisionClient, LocalOllamaVisionError
from app.ai.gateway.vision_client_factory import create_vision_review_client, get_vision_review_model
from app.config import settings


@pytest.mark.asyncio
async def test_local_ollama_review_sends_plain_base64_and_returns_content():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": '{"items":[]}'},
                "prompt_eval_count": 12,
                "eval_count": 4,
            },
        )

    client = LocalOllamaVisionClient()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    encoded = base64.b64encode(b"image-bytes").decode()

    result = await client.review_contact_sheet(
        prompt="只输出 JSON",
        contact_sheet_data_url=f"data:image/jpeg;base64,{encoded}",
        task_id="local-test",
    )

    assert captured["model"] == settings.LOCAL_VL_MODEL
    assert captured["stream"] is False
    assert captured["format"] == "json"
    assert captured["options"]["temperature"] == 0.1
    assert captured["messages"][0]["images"] == [encoded]
    assert "data:image" not in captured["messages"][0]["images"][0]
    assert result["content"] == '{"items":[]}'
    assert result["usage"] == {"prompt_eval_count": 12, "eval_count": 4}
    await client.close()


@pytest.mark.asyncio
async def test_local_ollama_rejects_invalid_data_url_before_request():
    client = LocalOllamaVisionClient()

    with pytest.raises(LocalOllamaVisionError, match="local_ollama_invalid_image_data_url"):
        await client.review_contact_sheet(prompt="JSON", contact_sheet_data_url="not-a-data-url")


def test_vision_client_factory_selects_all_supported_providers(monkeypatch):
    monkeypatch.setattr(settings, "VISION_REVIEW_PROVIDER", "local_ollama")
    assert isinstance(create_vision_review_client(), LocalOllamaVisionClient)
    assert get_vision_review_model() == settings.LOCAL_VL_MODEL

    monkeypatch.setattr(settings, "VISION_REVIEW_PROVIDER", "dashscope")
    assert isinstance(create_vision_review_client(), DashScopeVisionReviewClient)

    monkeypatch.setattr(settings, "VISION_REVIEW_PROVIDER", "rules")
    assert create_vision_review_client() is None
    assert get_vision_review_model() == "rules"
