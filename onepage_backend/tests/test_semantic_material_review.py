import base64

import pytest

from app.ai.gateway.dashscope_vision_client import build_image_data_url
from app.ai.pipeline.step1_content import build_semantic_result
from app.ai.pipeline.step4_material import infer_scene
from app.ai.pipeline.step5_layout import _select_materials_for_layout
from app.ai.pipeline.step4_material_review import (
    _build_contact_sheet,
    _local_preview_path,
    _normalize_vision_result,
    _parse_json_content,
    run_material_review,
)
from app.ai.pipeline.step6_repair import apply_final_page_quality_check, apply_semantic_guard
from app.ai.fallback.repairer import LayoutRepairer
from app.ai.fallback.validator import LayoutValidator
from app.models.material import Material
from app.services.material_service import MaterialService


def test_step1_study_semantics_include_avoid_tags():
    result = build_semantic_result(text="今天刷题复盘资料分析，给自己一点自信", text_analysis={}, mood="平静")

    assert result["scene"] == "self_growth"
    assert result["sub_scene"] == "study_reflection"
    assert result["intent"] == "self_encouragement"
    assert "study" in result["positive_tags"]
    assert "valentine" in result["avoid_tags"]
    assert result["semantic_constraints"]["avoid_romance"] is True


def test_step1_food_semantics_prioritizes_food_review():
    result = build_semantic_result(text="今天吃了铁锅炖，真棒！！！！", text_analysis={"scene": "家庭"}, mood="开心")

    assert result["scene"] == "daily_life"
    assert result["sub_scene"] == "food_review"
    assert result["intent"] == "food_record"
    assert "food" in result["positive_tags"]
    assert {"party", "festival", "bouquet", "gift", "ballet"}.issubset(set(result["avoid_tags"]))


def test_step1_health_recovery_semantics_are_gentle_and_strict():
    result = build_semantic_result(text="身体不舒服，喝了小柴胡，现在好一点", text_analysis={}, mood="平静")

    assert result["scene"] == "daily_life"
    assert result["sub_scene"] == "health_recovery"
    assert result["intent"] == "recovery_record"
    assert "healing" in result["positive_tags"]
    assert "business_sales" in result["avoid_tags"]


def test_step4_food_scene_overrides_family():
    scene = infer_scene(
        text="今天吃了一家很好吃的饺子店，和家人一起给他点赞",
        step1_scene_value="家庭",
        step1_sub_scene_value="food_review",
        weather="",
    )

    assert scene == "daily_life"


def test_material_tag_profile_marks_subject_sticker_not_background_safe():
    svc = MaterialService.__new__(MaterialService)
    material = Material(
        material_type="sticker",
        file_url="http://example.com/cat.png",
        style_tags=["可爱"],
        emotion_tags=["治愈"],
        scene_tags=["日常"],
        meta_info={
            "category": "动物",
            "display_name": "小猫贴纸",
            "semantic_tags": ["猫", "可爱"],
            "asset_width": 300,
            "asset_height": 300,
        },
    )

    profile = svc._material_tag_profile(material, quality={"density": "medium", "complexity": "low", "background_safe": None})

    assert profile["suggested_role"] == "focal_sticker"
    assert profile["background_safe"] is False
    assert "猫" in profile["keywords"]


def test_step5_selects_only_reviewed_candidates_and_respects_minimal():
    materials = {
        "fallback_mode": "neutral_minimal",
        "groups": [
            {
                "material_type": "sticker",
                "items": [
                    {"material_id": "focal", "file_url": "https://example.com/focal.png", "safe_role": "focal_sticker", "semantic_fit": 0.9, "visual_safety": 0.9},
                    {"material_id": "support", "file_url": "https://example.com/support.png", "safe_role": "supporting_sticker", "semantic_fit": 0.5, "visual_safety": 0.8},
                ],
            },
            {
                "material_type": "decoration",
                "items": [
                    {"material_id": "d1", "file_url": "https://example.com/d1.png", "semantic_fit": 0.7, "visual_safety": 0.9},
                    {"material_id": "d2", "file_url": "https://example.com/d2.png", "semantic_fit": 0.6, "visual_safety": 0.9},
                    {"material_id": "d3", "file_url": "https://example.com/d3.png", "semantic_fit": 0.5, "visual_safety": 0.9},
                ],
            },
        ],
        "rejected_materials": [{"material_id": "rejected"}],
    }

    selected = _select_materials_for_layout(materials)
    selected_ids = [item["material_id"] for item in selected]

    assert "focal" not in selected_ids
    assert "support" in selected_ids
    assert "rejected" not in selected_ids
    assert len([item for item in selected if item["material_id"].startswith("d")]) == 2


def test_validator_reports_element_extent_overflow():
    errors = LayoutValidator().validate(
        {
            "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
            "elements": [
                {"type": "sticker", "props": {"x": 1000, "y": 100, "w": 200, "h": 120}, "z_index": 20}
            ],
            "style": {"theme": "healing", "font": "handwriting"},
        }
    )

    assert any("x+w" in error for error in errors)


def test_repairer_neutral_minimal_does_not_add_focal_sticker():
    layout = {
        "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
        "elements": [{"type": "text", "props": {"content": "饺子店真好吃", "x": 80, "y": 400, "w": 800, "h": 120}, "z_index": 30}],
        "style": {"theme": "healing", "font": "handwriting"},
    }
    repaired = LayoutRepairer().repair(
        __import__("json").dumps(layout, ensure_ascii=False),
        [],
        asset_context={
            "fallback_mode": "neutral_minimal",
            "groups": [
                {
                    "material_type": "sticker",
                    "items": [
                        {"file_url": "http://example.com/focal.png", "safe_role": "focal_sticker", "score": 99},
                        {"file_url": "http://example.com/support.png", "safe_role": "supporting_sticker", "score": 50},
                    ],
                }
            ],
        },
    )

    urls = [element.get("props", {}).get("url") for element in repaired["elements"] if isinstance(element.get("props"), dict)]
    assert "http://example.com/focal.png" not in urls
    assert "http://example.com/support.png" in urls


@pytest.mark.asyncio
async def test_material_review_rejects_valentine_for_study():
    result = await run_material_review(
        {
            "task_id": "t-study",
            "input_json": {"text": "备考刷题复盘，今天也要进步"},
            "step1": build_semantic_result(text="备考刷题复盘，今天也要进步", text_analysis={}, mood="平静"),
            "step3": {"theme": "healing"},
            "step4": {
                "groups": [
                    {
                        "material_type": "sticker",
                        "items": [
                            {
                                "material_id": "s-valentine",
                                "display_name": "Happy Valentine's Day 爱心贴纸",
                                "category": "爱心星星",
                                "file_url": "http://example.com/v.png",
                                "preview_url": "http://example.com/v.png",
                            }
                        ],
                    }
                ]
            },
        }
    )

    assert result["fallback_mode"] == "neutral_minimal"
    assert result["reviewed_candidates"]["sticker"] == []
    assert result["rejected_materials"][0]["material_id"] == "s-valentine"
    assert "valentine" in result["rejected_materials"][0]["risk_flags"]


@pytest.mark.asyncio
async def test_material_review_downgrades_unsafe_background():
    result = await run_material_review(
        {
            "task_id": "t-bg",
            "input_json": {"text": "普通日常"},
            "step1": build_semantic_result(text="普通日常", text_analysis={}, mood="平静"),
            "step3": {},
            "step4": {
                "groups": [
                    {
                        "material_type": "background",
                        "items": [
                            {
                                "material_id": "bg-busy",
                                "display_name": "强图案背景",
                                "category": "背景",
                                "density": "high",
                                "complexity": "high",
                                "background_safe": False,
                                "file_url": "http://example.com/bg.png",
                                "preview_url": "http://example.com/bg.png",
                            }
                        ],
                    }
                ]
            },
        }
    )

    assert result["reviewed_candidates"]["background"] == []
    assert result["reviewed_candidates"]["decoration"][0]["material_id"] == "bg-busy"
    assert result["reviewed_candidates"]["decoration"][0]["decision"] == "downgrade"


@pytest.mark.asyncio
async def test_material_review_rejects_recovery_semantic_conflicts():
    result = await run_material_review(
        {
            "task_id": "t-health",
            "input_json": {"text": "身体不舒服，喝了小柴胡，现在好一点"},
            "step1": build_semantic_result(text="身体不舒服，喝了小柴胡，现在好一点", text_analysis={}, mood="平静"),
            "step3": {"theme": "healing"},
            "step4": {
                "groups": [
                    {
                        "material_type": "sticker",
                        "items": [
                            {"material_id": "congrats", "display_name": "おめでとう 祝福花束", "category": "花草"},
                            {"material_id": "sales", "display_name": "价格昂贵 business sale", "category": "图标符号"},
                            {"material_id": "tape", "display_name": "米白小胶带", "category": "胶带"},
                        ],
                    }
                ]
            },
        }
    )

    rejected_ids = {item["material_id"] for item in result["rejected_materials"]}
    assert {"congrats", "sales"}.issubset(rejected_ids)
    assert "tape" in {
        item["material_id"]
        for items in result["reviewed_candidates"].values()
        for item in items
    }


@pytest.mark.asyncio
async def test_material_review_vision_failure_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr("app.ai.pipeline.step4_material_review._vision_unavailable_reason", lambda: "")

    async def boom(**kwargs):
        raise RuntimeError("vision unavailable")

    monkeypatch.setattr("app.ai.pipeline.step4_material_review._run_vision_review", boom)
    result = await run_material_review(
        {
            "task_id": "t-vision",
            "input_json": {"text": "今天吃了好吃的饺子"},
            "step1": build_semantic_result(text="今天吃了好吃的饺子", text_analysis={}, mood="开心"),
            "step3": {},
            "step4": {
                "groups": [
                    {
                        "material_type": "sticker",
                        "items": [
                            {
                                "material_id": "food-1",
                                "display_name": "饺子小贴纸",
                                "category": "食物",
                                "file_url": "http://example.com/food.png",
                                "preview_url": "http://example.com/food.png",
                            }
                        ],
                    }
                ]
            },
        }
    )

    assert result["review_summary"]["vision_failed"] is True
    assert result["reviewed_candidates"]["sticker"][0]["material_id"] == "food-1"


@pytest.mark.asyncio
async def test_food_review_rejects_offtopic_materials_and_enters_minimal():
    result = await run_material_review(
        {
            "task_id": "t-food-offtopic",
            "input_json": {"text": "今天吃了一家很好吃的饺子店，给他点赞。开心"},
            "step1": build_semantic_result(text="今天吃了一家很好吃的饺子店，给他点赞。开心", text_analysis={"scene": "家庭"}, mood="开心"),
            "step3": {"theme": "healing"},
            "step4": {
                "groups": [
                    {
                        "material_type": "sticker",
                        "items": [
                            {"material_id": "party", "display_name": "party celebration", "category": "节日符号", "suggested_role": "focal_sticker"},
                            {"material_id": "family", "display_name": "family people", "category": "人物场景", "suggested_role": "focal_sticker"},
                            {"material_id": "ballet", "display_name": "ballet dancer", "category": "人物角色", "suggested_role": "focal_sticker"},
                            {"material_id": "crest", "display_name": "Japanese family crest chidori", "category": "图标符号", "suggested_role": "focal_sticker"},
                            {"material_id": "bear", "display_name": "可爱小熊", "category": "动物", "suggested_role": "focal_sticker"},
                        ],
                    },
                    {
                        "material_type": "decoration",
                        "items": [
                            {"material_id": "bouquet", "display_name": "祝福花束 gift bouquet", "category": "花草"},
                            {"material_id": "tape", "display_name": "暖色小胶带", "category": "胶带"},
                        ],
                    },
                ]
            },
        }
    )

    rejected_ids = {item["material_id"] for item in result["rejected_materials"]}
    assert {"party", "family", "ballet", "crest", "bouquet"}.issubset(rejected_ids)
    assert result["fallback_mode"] == "neutral_minimal"
    reviewed_ids = {
        item["material_id"]
        for items in result["reviewed_candidates"].values()
        for item in items
    }
    assert not reviewed_ids.intersection({"party", "family", "ballet", "crest", "bouquet"})
    assert len(result["reviewed_candidates"]["sticker"]) <= 1
    assert len(result["reviewed_candidates"]["decoration"]) <= 2


@pytest.mark.asyncio
async def test_food_review_keeps_strong_food_material_without_minimal():
    result = await run_material_review(
        {
            "task_id": "t-food-strong",
            "input_json": {"text": "今天吃了铁锅炖，真棒"},
            "step1": build_semantic_result(text="今天吃了铁锅炖，真棒", text_analysis={}, mood="开心"),
            "step3": {"theme": "healing"},
            "step4": {
                "groups": [
                    {
                        "material_type": "sticker",
                        "items": [
                            {
                                "material_id": "food-pot",
                                "display_name": "铁锅炖美食贴纸",
                                "category": "食物",
                                "suggested_role": "focal_sticker",
                                "file_url": "http://example.com/food.png",
                            }
                        ],
                    }
                ]
            },
        }
    )

    assert result["fallback_mode"] == "none"
    assert result["reviewed_candidates"]["sticker"][0]["material_id"] == "food-pot"
    assert result["reviewed_candidates"]["sticker"][0]["semantic_fit"] >= 0.65


@pytest.mark.asyncio
async def test_material_review_empty_candidates_neutral_minimal():
    result = await run_material_review(
        {
            "task_id": "t-empty",
            "input_json": {"text": "今天记录一点日常"},
            "step1": build_semantic_result(text="今天记录一点日常", text_analysis={}, mood="平静"),
            "step3": {},
            "step4": {"groups": []},
        }
    )

    assert result["fallback_mode"] == "neutral_minimal"
    assert result["groups"] == []


def test_step6_semantic_guard_removes_risky_material():
    layout = {
        "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
        "elements": [
            {"type": "sticker", "props": {"url": "http://example.com/valentine.png", "x": 80, "y": 80, "w": 160, "h": 160}},
            {"type": "text", "props": {"content": "刷题复盘", "x": 80, "y": 320, "w": 800, "h": 120}},
        ],
        "style": {"theme": "healing"},
    }
    guarded = apply_semantic_guard(
        layout,
        ctx={
            "task_id": "t-guard",
            "step1": build_semantic_result(text="刷题复盘", text_analysis={}, mood="平静"),
        },
        asset_context={
            "groups": [
                {
                    "material_type": "sticker",
                    "items": [
                        {
                            "file_url": "http://example.com/valentine.png",
                            "risk_flags": ["valentine"],
                            "display_name": "Happy Valentine's Day",
                        }
                    ],
                }
            ]
        },
    )

    assert len(guarded["elements"]) == 1
    assert guarded["elements"][0]["type"] == "text"


def test_step6_food_guard_removes_offtopic_and_empty_blocks():
    layout = {
        "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
        "elements": [
            {"type": "sticker", "props": {"url": "http://example.com/party.png", "x": 80, "y": 80, "w": 160, "h": 160}},
            {"type": "shape", "props": {"x": 80, "y": 300, "w": 880, "h": 260, "background": "#F0E6D6"}},
            {"type": "text", "props": {"content": "铁锅炖真好吃", "x": 80, "y": 600, "w": 800, "h": 120}},
        ],
        "style": {"theme": "healing"},
    }
    guarded = apply_semantic_guard(
        layout,
        ctx={
            "task_id": "t-food-guard",
            "step1": build_semantic_result(text="今天吃了铁锅炖，真棒", text_analysis={}, mood="开心"),
        },
        asset_context={
            "groups": [
                {
                    "material_type": "sticker",
                    "items": [
                        {
                            "file_url": "http://example.com/party.png",
                            "risk_flags": ["party"],
                            "display_name": "party celebration",
                        }
                    ],
                }
            ]
        },
    )

    assert [element["type"] for element in guarded["elements"]] == ["text"]


def test_final_quality_check_removes_empty_rejected_and_extra_focal():
    layout = {
        "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
        "elements": [
            {"type": "sticker", "props": {"url": "", "x": 40, "y": 40, "w": 120, "h": 120}},
            {"type": "sticker", "props": {"url": "http://example.com/rejected.png", "x": 80, "y": 80, "w": 160, "h": 160}},
            {"type": "sticker", "props": {"url": "http://example.com/focal-a.png", "x": 80, "y": 280, "w": 160, "h": 160}},
            {"type": "sticker", "props": {"url": "http://example.com/focal-b.png", "x": 260, "y": 280, "w": 160, "h": 160}},
            {"type": "text", "props": {"content": "今天好一点", "x": 80, "y": 520, "w": 800, "h": 120}},
        ],
    }
    checked = apply_final_page_quality_check(
        layout,
        ctx={
            "task_id": "t-quality",
            "journal_context": {"weather_success": False},
            "step4_review": {
                "rejected_materials": [{"file_url": "http://example.com/rejected.png"}],
                "groups": [
                    {
                        "material_type": "sticker",
                        "items": [
                            {"file_url": "http://example.com/focal-a.png", "safe_role": "focal_sticker"},
                            {"file_url": "http://example.com/focal-b.png", "safe_role": "focal_sticker"},
                        ],
                    }
                ],
            },
        },
        asset_context={
            "groups": [
                {
                    "material_type": "sticker",
                    "items": [
                        {"file_url": "http://example.com/focal-a.png", "safe_role": "focal_sticker"},
                        {"file_url": "http://example.com/focal-b.png", "safe_role": "focal_sticker"},
                    ],
                }
            ]
        },
    )

    urls = [element.get("props", {}).get("url") for element in checked["elements"] if isinstance(element.get("props"), dict)]
    assert "" not in urls
    assert "http://example.com/rejected.png" not in urls
    assert urls.count("http://example.com/focal-a.png") == 1
    assert "http://example.com/focal-b.png" not in urls


def test_contact_sheet_uses_local_file_and_ignores_localhost_url(tmp_path):
    image_path = tmp_path / "preview.png"
    image_path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))
    item = {
        "material_id": "m1",
        "name": "本地预览",
        "type": "sticker",
        "category": "花草",
        "_source": {
            "origin_path": str(image_path),
            "preview_url": "http://127.0.0.1:8000/api/materials/m1/preview",
        },
    }

    assert _local_preview_path({"preview_url": "http://127.0.0.1:8000/api/materials/m1/preview"}) is None
    sheet = _build_contact_sheet([item])
    assert sheet is not None
    data_uri, sheet_items = sheet
    assert data_uri.startswith("data:image/jpeg;base64,")
    assert "127.0.0.1" not in data_uri
    assert sheet_items[0]["label"] == "A01"
    assert sheet_items[0]["material_id"] == "m1"


def test_dashscope_data_url_has_mime_prefix():
    data_url = build_image_data_url(b"abc123", "image/jpeg")

    assert data_url.startswith("data:image/jpeg;base64,")
    assert "abc123" not in data_url


def test_parse_vision_json_handles_markdown_wrapper():
    parsed = _parse_json_content('prefix```json\n{"items":[{"label":"A01","decision":"keep"}]}\n```suffix')

    assert parsed["items"][0]["label"] == "A01"


def test_normalize_vision_result_ignores_unknown_labels_and_clamps_scores():
    normalized = _normalize_vision_result(
        {
            "items": [
                {"label": "A01", "decision": "reject", "semantic_fit": 9, "visual_safety": -1, "safe_role": "none"},
                {"label": "B99", "decision": "keep"},
            ]
        },
        label_map={"A01": {"material_id": "m1"}},
    )

    assert len(normalized["items"]) == 1
    assert normalized["items"][0]["material_id"] == "m1"
    assert normalized["items"][0]["semantic_fit"] == 1.0
    assert normalized["items"][0]["visual_safety"] == 0.0
