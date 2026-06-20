import json

import pytest

from app.ai.fallback.validator import LayoutValidator
from app.ai.layout.compiler import compile_layout_template
from app.ai.layout.template_specs import TEMPLATE_SPECS
from app.ai.pipeline import step5_layout
from app.ai.pipeline.step5_layout import _parse_layout_decision, _select_materials_for_layout
from app.ai.pipeline.step6_repair import run_validate_and_repair
from app.ai.prompts.layout_fewshots import build_layout_policy, select_layout_fewshots, selected_material_bundle
from app.config import settings


def _material(material_id: str, role: str, material_type: str, **overrides):
    return {
        "material_id": material_id,
        "material_type": material_type,
        "safe_role": role,
        "suggested_role": role,
        "file_url": f"https://assets.example.com/{material_id}.png",
        "semantic_fit": 0.9,
        "visual_safety": 0.9,
        "background_safe": True,
        "asset_width": 600,
        "asset_height": 600,
        **overrides,
    }


def _groups(*items):
    grouped = {"background": [], "sticker": [], "decoration": []}
    for item in items:
        grouped[item["material_type"]].append(item)
    return [{"material_type": key, "items": value} for key, value in grouped.items() if value]


def _authoritative_context():
    return {
        "date_text": "2026.06.20 周六",
        "weather_text": "多云",
        "weather_icon": "⛅",
        "weather_icon_key": "cloudy",
        "weather_success": True,
    }


def test_cat_home_medium_selects_watermark_center_template():
    selected = selected_material_bundle(
        [
            _material("bg", "background", "background"),
            _material("cat", "focal_sticker", "sticker"),
            _material("flower", "decoration", "decoration"),
        ]
    )
    candidates, templates = select_layout_fewshots(
        content_text="今天猫猫一直趴在键盘上，最后抱着它一起看电影，感觉被治愈了。",
        semantic={"scene": "daily_life", "positive_tags": ["home", "pet"]},
        style={"theme": "healing"},
        selected_materials=selected,
        fallback_mode="none",
    )

    assert candidates[0]["id"] == "healing_watermark_center_sticker"
    assert templates[0]["id"] == "healing_watermark_center_sticker"
    assert "slots" not in templates[0]


def test_compiler_is_deterministic_and_uses_selected_assets_only():
    items = [
        _material("bg", "background", "background", asset_width=1200, asset_height=900),
        _material("cat", "focal_sticker", "sticker"),
        _material("flower", "decoration", "decoration"),
    ]
    bundle = selected_material_bundle(items)
    kwargs = {
        "template_id": "healing_watermark_center_sticker",
        "title": "被猫治愈的一天",
        "body": "今天猫猫一直趴在键盘上，最后抱着它一起看电影。",
        "mood": "开心",
        "authoritative_context": _authoritative_context(),
        "selected_materials": bundle,
        "style": {"theme": "healing"},
        "optional_slots": {"decoration": True},
    }

    first = compile_layout_template(**kwargs)
    second = compile_layout_template(**kwargs)

    assert first == second
    assert first["template_id"] == "healing_watermark_center_sticker"
    used_ids = {
        element["props"]["material_id"]
        for element in first["elements"]
        if element["type"] in {"image", "sticker", "decoration"}
    }
    assert used_ids == {"bg", "cat", "flower"}
    assert not LayoutValidator().validate(first, asset_context={"selected_materials": items})


def test_compiler_preserves_bottom_whitespace_and_full_body():
    body = "这是一段需要完整保留的长正文。" * 16
    layout = compile_layout_template(
        template_id="text_forward_long_form",
        title="一段需要慢慢整理并认真记录下来的很长标题",
        body=body,
        mood="平静",
        authoritative_context=_authoritative_context(),
        selected_materials=selected_material_bundle([]),
        style={"theme": "minimal"},
    )

    body_element = next(item for item in layout["elements"] if item.get("props", {}).get("role") == "body")
    assert body_element["props"]["content"] == body
    assert body_element["props"]["size"] <= 34
    assert body_element["props"]["y"] + body_element["props"]["h"] <= layout["page"]["height"] * 0.82
    assert not LayoutValidator().validate(layout)


def test_optional_slots_can_be_disabled_without_placeholder_elements():
    decoration = _material("flower", "decoration", "decoration")
    layout = compile_layout_template(
        template_id="neutral_minimal_record",
        title="今天的一页",
        body="今天吃了一碗热乎乎的饺子。",
        mood="开心",
        authoritative_context=_authoritative_context(),
        selected_materials=selected_material_bundle([decoration]),
        style={"theme": "healing"},
        optional_slots={"decoration": False},
    )

    assert not any(item.get("props", {}).get("role") == "decoration" for item in layout["elements"])


def test_empty_optional_slots_use_conservative_template_defaults():
    items = [
        _material("bg", "background", "background"),
        _material("cat", "focal_sticker", "sticker"),
        _material("tape", "tape", "decoration"),
        _material("friend", "supporting_sticker", "sticker"),
        _material("flower", "decoration", "decoration"),
        _material("frame", "frame", "decoration"),
    ]
    layout = compile_layout_template(
        template_id="healing_watermark_center_sticker",
        title="被猫治愈的一天",
        body="今天和猫一起看电影。",
        mood="开心",
        authoritative_context=_authoritative_context(),
        selected_materials=selected_material_bundle(items),
        style={"theme": "healing"},
        optional_slots={},
    )

    material_roles = {
        item["props"]["role"]
        for item in layout["elements"]
        if item["type"] in {"image", "sticker", "decoration"}
    }
    assert material_roles == {"background", "focal_sticker", "tape"}


def test_invalid_optional_slot_values_fall_back_to_template_defaults():
    decision = _parse_layout_decision(
        json.dumps(
            {
                "template_id": "healing_watermark_center_sticker",
                "title": "被猫治愈的一天",
                "body": "今天和猫一起看电影。",
                "optional_slots": {"decoration": "true", "frame": 1, "tape": False},
            }
        ),
        candidate_ids=["healing_watermark_center_sticker"],
        content_text="今天和猫一起看电影。",
        title_hint="今天的一页",
    )

    assert decision is not None
    assert decision["optional_slots"] == {"tape": False}


def test_layout_decision_accepts_only_candidate_template():
    decision = _parse_layout_decision(
        json.dumps({"template_id": "neutral_minimal_record", "title": "饺子小记", "body": "今天吃了饺子。"}),
        candidate_ids=["neutral_minimal_record"],
        content_text="今天吃了饺子。",
        title_hint="今天的一页",
    )
    invalid = _parse_layout_decision(
        json.dumps({"template_id": "invented", "title": "错误模板"}),
        candidate_ids=["neutral_minimal_record"],
        content_text="今天吃了饺子。",
        title_hint="今天的一页",
    )

    assert decision["template_id"] == "neutral_minimal_record"
    assert invalid is None


@pytest.mark.asyncio
async def test_step5_model_only_decides_template_and_copy(monkeypatch):
    monkeypatch.setattr(settings, "LAYOUT_ENGINE_VERSION", "v1")
    items = [
        _material("bg", "background", "background", asset_width=1200, asset_height=900),
        _material("cat", "focal_sticker", "sticker"),
    ]

    async def fake_qwen(prompt):
        assert '"x"' not in prompt
        assert "https://assets.example.com" not in prompt
        return json.dumps(
            {
                "template_id": "healing_watermark_center_sticker",
                "title": "被猫治愈的一天",
                "body": "今天和猫一起看电影。",
                "optional_slots": {"background": True, "focal_sticker": True},
            },
            ensure_ascii=False,
        )

    async def forbidden_deepseek(prompt):
        raise AssertionError("fallback model should not be called")

    monkeypatch.setattr(step5_layout, "_call_qwen", fake_qwen)
    monkeypatch.setattr(step5_layout, "_call_deepseek", forbidden_deepseek)
    ctx = {
        "task_id": "step5-template",
        "input_json": {"text": "今天和猫一起看电影。", "mood": "开心"},
        "step1": {"scene": "daily_life", "positive_tags": ["home", "pet"], "topic": "猫咪电影日"},
        "step2": {"primary_emotion": "happy"},
        "step3": {"theme": "healing"},
        "step4_review": {"groups": _groups(*items), "fallback_mode": "none", "rejected_materials": []},
        "journal_context": {
            "weather_success": True,
            "weather_status": "success",
            "datetime": {"date": "2026-06-20"},
            "journal_header": {"date_text": "2026.06.20 周六", "weather_text": "多云", "weather_icon": "⛅"},
            "weather": {"text": "多云", "icon": "⛅", "icon_key": "cloudy"},
            "location": {"city": "深圳市", "district": "福田区"},
        },
    }

    layout = json.loads(await step5_layout.run_layout_generation(ctx))

    assert layout["template_id"] == "healing_watermark_center_sticker"
    assert ctx["step5_decision"]["title"] == "被猫治愈的一天"
    assert {
        item["props"]["material_id"]
        for item in layout["elements"]
        if item["type"] in {"image", "sticker", "decoration"}
    } == {"bg", "cat"}


@pytest.mark.asyncio
async def test_step6_conservative_path_keeps_compiled_coordinates():
    items = [
        _material("bg", "background", "background", asset_width=1200, asset_height=900),
        _material("cat", "focal_sticker", "sticker"),
    ]
    layout = compile_layout_template(
        template_id="healing_watermark_center_sticker",
        title="被猫治愈的一天",
        body="今天和猫一起看电影。",
        mood="开心",
        authoritative_context=_authoritative_context(),
        selected_materials=selected_material_bundle(items),
        style={"theme": "healing"},
    )
    focal_before = next(item for item in layout["elements"] if item.get("props", {}).get("role") == "focal_sticker")["props"].copy()
    ctx = {
        "task_id": "template-test",
        "step5": json.dumps(layout, ensure_ascii=False),
        "step4_review": {"groups": _groups(*items), "selected_materials": items, "fallback_mode": "none"},
        "journal_context": {
            "weather_success": True,
            "weather_status": "success",
            "datetime": {"date": "2026-06-20"},
            "journal_header": {"date_text": "2026.06.20 周六", "weather_text": "多云", "weather_icon": "⛅"},
            "weather": {"text": "多云", "icon": "⛅", "icon_key": "cloudy"},
        },
        "input_json": {"text": "今天和猫一起看电影。"},
    }

    repaired = await run_validate_and_repair(ctx)
    focal_after = next(item for item in repaired["elements"] if item.get("props", {}).get("role") == "focal_sticker")["props"]

    assert repaired["template_id"] == layout["template_id"]
    assert {key: focal_after[key] for key in ("x", "y", "w", "h")} == {key: focal_before[key] for key in ("x", "y", "w", "h")}


def test_background_safe_false_is_not_selected():
    materials = {
        "groups": _groups(
            _material("unsafe", "background", "background", background_safe=False),
            _material("safe", "background", "background", semantic_fit=0.7),
        ),
        "fallback_mode": "none",
    }
    assert [item["material_id"] for item in _select_materials_for_layout(materials)] == ["safe"]


def test_long_title_policy_wraps_and_reduces_size():
    policy = build_layout_policy(
        content_text="普通正文",
        title_hint="这是一个明显超过正常长度并且需要自动换行的手帐标题",
        selected_materials={},
    )
    assert policy["title"]["allow_wrap"] is True
    assert policy["title"]["max_lines"] == 2
    assert policy["title"]["suggested_size"] == 48


def test_all_template_specs_have_executable_slots():
    for spec in TEMPLATE_SPECS:
        assert {"date", "mood", "weather", "title", "body"}.issubset(spec["slots"])
        assert spec["page_style"]["background"].startswith("#")
