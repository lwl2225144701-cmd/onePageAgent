from copy import deepcopy

from app.ai.fallback.validator import LayoutValidator
from app.ai.pipeline.step5_layout import _select_materials_for_layout
from app.ai.prompts.layout_fewshots import (
    LAYOUT_FEWSHOTS,
    build_layout_policy,
    render_layout_fewshot,
    select_layout_fewshots,
    selected_material_bundle,
)


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


def test_cat_home_medium_selects_watermark_center_fewshot():
    selected = selected_material_bundle(
        [
            _material("bg", "background", "background"),
            _material("cat", "focal_sticker", "sticker"),
            _material("flower", "decoration", "decoration"),
        ]
    )
    candidates, fewshots = select_layout_fewshots(
        content_text="今天猫猫一直趴在键盘上，最后抱着它一起看电影，感觉被治愈了。",
        semantic={"scene": "daily_life", "positive_tags": ["home", "pet"]},
        style={"theme": "healing"},
        selected_materials=selected,
        fallback_mode="none",
    )

    assert candidates[0]["id"] == "healing_watermark_center_sticker"
    assert fewshots[0]["id"] == "healing_watermark_center_sticker"
    assert not LayoutValidator().validate(fewshots[0]["output"])


def test_short_text_selects_short_note_pattern():
    _, fewshots = select_layout_fewshots(
        content_text="今天很开心。",
        semantic={"scene": "daily_life"},
        style={"theme": "cute"},
        selected_materials=selected_material_bundle([]),
        fallback_mode="none",
    )

    assert any(item["id"] == "short_note_with_corner_accent" for item in fewshots)


def test_long_content_expands_body_and_shrinks_focal():
    short = build_layout_policy(
        content_text="今天很好。",
        title_hint="小确幸",
        selected_materials={"focal_sticker": {"material_id": "cat"}},
    )
    long = build_layout_policy(
        content_text="这是一段需要完整保留的长正文。" * 16,
        title_hint="一段需要慢慢整理并认真记录下来的很长标题",
        selected_materials={"focal_sticker": {"material_id": "cat"}},
    )

    assert long["content_length"] == "long"
    assert long["body"]["suggested_size"] < short["body"]["suggested_size"]
    assert long["focal_sticker"]["max_width"] < short["focal_sticker"]["max_width"]
    assert long["title"]["suggested_size"] < short["title"]["suggested_size"]


def test_fewshot_omits_missing_decoration():
    example = deepcopy(LAYOUT_FEWSHOTS[0])
    example["input"]["selected_materials"]["decorations"] = []
    output = render_layout_fewshot(example)["output"]

    assert not any(
        element["type"] == "decoration" and element.get("props", {}).get("role") == "decoration"
        for element in output["elements"]
    )


def test_fewshot_omits_missing_frame():
    example = deepcopy(LAYOUT_FEWSHOTS[0])
    example["input"]["selected_materials"]["frame"] = {}
    output = render_layout_fewshot(example)["output"]

    assert not any(element.get("props", {}).get("role") == "frame" for element in output["elements"])


def test_background_safe_false_is_not_selected():
    materials = {
        "groups": _groups(
            _material("unsafe", "background", "background", background_safe=False),
            _material("safe", "background", "background", semantic_fit=0.7),
        ),
        "fallback_mode": "none",
    }

    selected = _select_materials_for_layout(materials)

    assert [item["material_id"] for item in selected] == ["safe"]


def test_long_title_policy_wraps_and_reduces_size():
    policy = build_layout_policy(
        content_text="普通正文",
        title_hint="这是一个明显超过正常长度并且需要自动换行的手帐标题",
        selected_materials={},
    )

    assert policy["title"]["allow_wrap"] is True
    assert policy["title"]["max_lines"] == 2
    assert policy["title"]["suggested_size"] == 48


def test_invalid_selected_material_is_filtered_before_prompt():
    materials = {
        "groups": _groups(
            _material("missing-url", "focal_sticker", "sticker", file_url=""),
            _material("zero-size", "decoration", "decoration", asset_width=0),
            _material("valid", "supporting_sticker", "sticker"),
        ),
        "fallback_mode": "none",
    }

    selected = _select_materials_for_layout(materials)

    assert [item["material_id"] for item in selected] == ["valid"]


def test_validator_rejects_asset_outside_selected_materials():
    layout = {
        "page": {"width": 1080, "height": 1920, "background": "#F7F3EE"},
        "elements": [
            {
                "type": "sticker",
                "props": {
                    "material_id": "invented",
                    "url": "https://assets.example.com/invented.png",
                    "role": "focal_sticker",
                    "x": 380,
                    "y": 600,
                    "w": 300,
                    "h": 300,
                },
                "z_index": 22,
            }
        ],
        "style": {"theme": "healing", "font": "handwriting"},
    }
    selected = _material("cat", "focal_sticker", "sticker")

    errors = LayoutValidator().validate(layout, asset_context={"selected_materials": [selected]})

    assert any("material_id is not in selected_materials" in error for error in errors)
    assert any("url is not in selected_materials" in error for error in errors)
