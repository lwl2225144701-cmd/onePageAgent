import json
import pytest

from app.ai.fallback.templates import get_fallback_layout
from app.ai.fallback.validator import LayoutValidator
from app.ai.fallback.repairer import LayoutRepairer
from app.ai.pipeline.step6_repair import run_validate_and_repair


def test_get_fallback_layout():
    layout = get_fallback_layout("happy")
    assert "page" in layout
    assert "elements" in layout
    assert "style" in layout
    assert layout["page"]["width"] == 1080
    assert layout["style"]["theme"] == "warm"


def test_get_default_layout():
    layout = get_fallback_layout("nonexistent")
    assert layout["style"]["theme"] == "healing"


def test_validator_valid_layout():
    validator = LayoutValidator()
    repairer = LayoutRepairer()
    layout = repairer.repair(json.dumps(get_fallback_layout("neutral"), ensure_ascii=False), [])
    errors = validator.validate(layout)
    assert len(errors) == 0


def test_validator_invalid_layout():
    validator = LayoutValidator()
    errors = validator.validate({})
    assert len(errors) > 0


def test_validator_allows_background_image_under_text():
    validator = LayoutValidator()
    errors = validator.validate(
        {
            "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
            "elements": [
                {
                    "type": "image",
                    "props": {"url": "http://example.com/bg.svg", "x": 0, "y": 0, "w": 1080, "h": 720},
                    "z_index": 0,
                },
                {
                    "type": "text",
                    "props": {"content": "hello", "x": 80, "y": 840, "w": 920, "h": 96, "size": 42},
                    "z_index": 30,
                },
            ],
            "style": {"theme": "healing", "font": "handwriting"},
        }
    )
    assert errors == []


def test_repairer_missing_fields():
    repairer = LayoutRepairer()
    repaired = repairer.repair('{"style": {}}', [])
    assert repaired is not None
    assert "page" in repaired
    assert "elements" in repaired
    assert repaired["page"]["width"] == 1080
    assert repaired["style"]["theme"] == "healing"


def test_repairer_trailing_commas():
    repairer = LayoutRepairer()
    repaired = repairer.repair('{"page": {"width": 1080,}, "elements": [], "style": {"theme": "healing", "font": "handwriting",},}', [])
    assert repaired is not None
    assert repaired["page"]["width"] == 1080


def test_repairer_extract_from_markdown():
    repairer = LayoutRepairer()
    raw = '```json\n{"page": {"width": 1080, "height": 1920, "background": "#FAF6F0"}, "elements": [], "style": {"theme": "healing", "font": "handwriting"}}\n```'
    repaired = repairer.repair(raw, [])
    assert repaired is not None
    assert repaired["page"]["width"] == 1080


def test_full_fallback_pipeline():
    """Test the complete validation/repair/fallback loop."""
    validator = LayoutValidator()
    repairer = LayoutRepairer()

    emotion = "neutral"
    fallback = get_fallback_layout(emotion)

    # Simulate repair of fallback
    repaired = repairer.repair(json.dumps(fallback, ensure_ascii=False), [])
    assert repaired is not None
    errors = validator.validate(repaired)
    assert len(errors) == 0, f"Fallback template has errors after repair: {errors}"
    assert repaired["page"]["width"] == 1080


def test_repairer_replaces_unknown_material_urls_with_candidates():
    repairer = LayoutRepairer()
    raw = json.dumps(
        {
            "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
            "elements": [
                {
                    "type": "sticker",
                    "props": {"url": "/fake/sticker.png", "x": 100, "y": 100, "w": 120, "h": 120},
                    "z_index": 20,
                }
            ],
            "style": {"theme": "healing", "font": "handwriting"},
        },
        ensure_ascii=False,
    )
    repaired = repairer.repair(
        raw,
        [],
        asset_context={
            "groups": [
                {
                    "material_type": "sticker",
                    "items": [{"file_url": "http://127.0.0.1:9000/onepage-materials/materials/user/sticker/a.png"}],
                }
            ],
            "input_image_urls": [],
        },
    )
    assert repaired is not None
    assert repaired["elements"][0]["props"]["url"] == "http://127.0.0.1:9000/onepage-materials/materials/user/sticker/a.png"


def test_repairer_injects_preferred_background_image():
    repairer = LayoutRepairer()
    repaired = repairer.repair(
        json.dumps(
            {
                "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
                "elements": [],
                "style": {"theme": "healing", "font": "handwriting"},
            },
            ensure_ascii=False,
        ),
        [],
        asset_context={
            "groups": [
                {
                    "material_type": "background",
                    "items": [{"file_url": "http://127.0.0.1:8000/api/materials/bg-1/asset"}],
                }
            ],
            "input_image_urls": [],
        },
    )
    assert repaired is not None
    image_elements = [item for item in repaired["elements"] if item.get("type") == "image"]
    assert image_elements
    assert image_elements[0]["props"]["url"] == "http://127.0.0.1:8000/api/materials/bg-1/asset"


def test_repairer_swaps_duplicate_stickers_with_alternative_candidate():
    repairer = LayoutRepairer()
    repaired = repairer.repair(
        json.dumps(
            {
                "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
                "elements": [
                    {"type": "sticker", "props": {"url": "http://127.0.0.1:8000/api/materials/s-1/asset", "x": 50, "y": 50, "w": 180, "h": 180}, "z_index": 20},
                    {"type": "sticker", "props": {"url": "http://127.0.0.1:8000/api/materials/s-1/asset", "x": 60, "y": 60, "w": 180, "h": 180}, "z_index": 21},
                ],
                "style": {"theme": "healing", "font": "handwriting"},
            },
            ensure_ascii=False,
        ),
        [],
        asset_context={
            "groups": [
                {
                    "material_type": "sticker",
                    "items": [
                        {"file_url": "http://127.0.0.1:8000/api/materials/s-1/asset"},
                        {"file_url": "http://127.0.0.1:8000/api/materials/s-2/asset"},
                    ],
                }
            ],
            "input_image_urls": [],
        },
    )
    assert repaired is not None
    sticker_urls = [item.get("props", {}).get("url") for item in repaired["elements"] if item.get("type") == "sticker"]
    assert sticker_urls == [
        "http://127.0.0.1:8000/api/materials/s-1/asset",
        "http://127.0.0.1:8000/api/materials/s-2/asset",
    ]


def test_repairer_repositions_sticker_away_from_text():
    repairer = LayoutRepairer()
    repaired = repairer.repair(
        json.dumps(
            {
                "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
                "elements": [
                    {"type": "text", "props": {"content": "正文", "x": 80, "y": 700, "w": 920, "h": 180, "size": 42}, "z_index": 30},
                    {"type": "sticker", "props": {"url": "http://127.0.0.1:8000/api/materials/s-1/asset", "x": 120, "y": 720, "w": 220, "h": 220}, "z_index": 20},
                ],
                "style": {"theme": "healing", "font": "handwriting"},
            },
            ensure_ascii=False,
        ),
        [],
        asset_context={
            "groups": [
                {
                    "material_type": "sticker",
                    "items": [{"file_url": "http://127.0.0.1:8000/api/materials/s-1/asset"}],
                }
            ],
            "input_image_urls": [],
        },
    )
    assert repaired is not None
    text = repaired["elements"][0]["props"]
    sticker = repaired["elements"][1]["props"]
    assert sticker["y"] + sticker["h"] <= text["y"] or sticker["y"] >= text["y"] + text["h"] or sticker["x"] + sticker["w"] <= text["x"] or sticker["x"] >= text["x"] + text["w"]


def test_repairer_adds_minimum_stickers_and_decorations_from_candidates():
    repairer = LayoutRepairer()
    repaired = repairer.repair(
        json.dumps(
            {
                "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
                "elements": [
                    {"type": "text", "props": {"content": "今天吃饺子", "x": 80, "y": 760, "w": 920, "h": 120, "size": 42}, "z_index": 30}
                ],
                "style": {"theme": "healing", "font": "handwriting"},
            },
            ensure_ascii=False,
        ),
        [],
        asset_context={
            "groups": [
                {
                    "material_type": "sticker",
                    "items": [
                        {"file_url": "http://127.0.0.1:8000/api/materials/s-1/asset", "suggested_role": "focal_sticker", "suggested_zone": "center", "suggested_size": "large", "suggested_z_index": 22, "density": "low", "importance": "focal"},
                        {"file_url": "http://127.0.0.1:8000/api/materials/s-2/asset", "suggested_role": "supporting_sticker", "suggested_zone": "top_right", "suggested_size": "medium", "suggested_z_index": 24, "density": "low", "importance": "supporting"},
                    ],
                },
                {
                    "material_type": "decoration",
                    "items": [
                        {"file_url": "http://127.0.0.1:8000/api/materials/d-1/asset", "suggested_role": "decoration", "suggested_zone": "top", "suggested_size": "small", "suggested_z_index": 10, "density": "low", "importance": "decorative"},
                        {"file_url": "http://127.0.0.1:8000/api/materials/d-2/asset", "suggested_role": "decoration", "suggested_zone": "bottom_right", "suggested_size": "small", "suggested_z_index": 11, "density": "low", "importance": "decorative"},
                    ],
                },
            ],
            "input_image_urls": [],
        },
    )

    assert repaired is not None
    assert len([item for item in repaired["elements"] if item.get("type") == "sticker"]) == 2
    assert len([item for item in repaired["elements"] if item.get("type") == "decoration"]) == 2


@pytest.mark.asyncio
async def test_step6_fallback_uses_candidate_asset_urls():
    result = await run_validate_and_repair(
        {
            "step5": "not-json",
            "step2": {"primary_emotion": "happy"},
            "step4": {
                "groups": [
                    {
                        "material_type": "sticker",
                        "items": [{"file_url": "http://127.0.0.1:9000/onepage-materials/materials/user/sticker/a.png"}],
                    }
                ]
            },
            "input_json": {"text": "今天很好", "page_date": "2026-05-21", "image_urls": []},
        }
    )
    sticker_urls = [item.get("props", {}).get("url") for item in result.get("elements", []) if item.get("type") == "sticker"]
    assert sticker_urls == ["http://127.0.0.1:9000/onepage-materials/materials/user/sticker/a.png"]
