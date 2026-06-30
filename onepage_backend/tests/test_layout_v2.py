import json
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from app.ai.layout_v2.catalog import get_template
from app.ai.layout_v2.compiler import compile_layout_v2
from app.ai.layout_v2.enums import MaterialRole
from app.ai.layout_v2.material_binder import bind_materials_for_template
from app.ai.layout_v2.material_retriever import score_candidate
from app.ai.layout_v2.material_retriever import normalize_material_metadata
from app.ai.layout_v2.material_reviewer import review_material_role_groups
from app.ai.layout_v2.resolver import resolve_layout_plans
from app.ai.layout_v2.schemas import LayoutPlan, MaterialCandidate
from app.ai.layout_v2.template_filter import filter_templates
from app.ai.layout_v2.validator import validate_layout_v2
from app.ai.layout_v2.visual_brief import build_visual_brief
from app.ai.pipeline import step5_layout
from app.ai.pipeline.step4_material import run_material_matching
from app.ai.pipeline.step4_material_review import run_material_review
from app.ai.pipeline.step6_repair import run_validate_and_repair
from scripts.backfill_material_visual_metadata import (
    calculate_visual_bbox,
    normalize_visual_payload,
    parse_batch_json,
)


def candidate(material_id: str, role: MaterialRole, **metadata_overrides) -> MaterialCandidate:
    metadata = {
        "subjects": [],
        "actions": [],
        "scenes": [],
        "objects": [],
        "suggested_role": role.value,
        "background_safe": role is MaterialRole.BACKGROUND,
        "visual_style": "healing",
        "color_tone": "warm",
        "complexity": "low",
        "density": "low",
        "visual_bbox": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.8},
        "annotation_version": "v2",
        **metadata_overrides,
    }
    return MaterialCandidate.model_validate(
        {
            "material_id": material_id,
            "role": role,
            "file_url": f"https://assets.example.com/{material_id}.png",
            "preview_url": f"https://assets.example.com/{material_id}.png",
            "mime_type": "image/png",
            "semantic_score": 0.9,
            "style_score": 0.8,
            "total_score": 0.9,
            "metadata": metadata,
            "asset_width": 800,
            "asset_height": 600,
        }
    )


def authoritative_context():
    return {
        "date_text": "2026.06.20 周六",
        "weather_success": True,
        "weather_text": "多云",
        "weather_icon": "⛅",
        "weather_icon_key": "cloudy",
    }


def _test_brief(
    text: str,
    mood: str,
    *,
    scene: str = "daily_life",
    sub_scene: str = "general_daily",
    subject: str = "",
    action: str = "",
    environment: list[str] | None = None,
    objects: list[str] | None = None,
    concepts: list[str] | None = None,
    title: str = "今天的一页",
):
    return build_visual_brief(
        text=text,
        mood=mood,
        semantic={
            "scene": scene,
            "sub_scene": sub_scene,
            "primary_subject": subject,
            "primary_action": action,
            "environment": environment or [],
            "objects": objects or [],
            "required_concepts": concepts or [],
            "visual_keywords": concepts or [],
            "title_hint": title,
            "topic": title,
        },
    )


def test_visual_brief_keeps_emotion_out_of_subject_recall():
    brief = _test_brief(
        "今天要出门去玩咯！！！你说应该去哪里玩呢",
        "兴奋",
        scene="outing",
        sub_scene="weekend_leisure",
        action="散步、旅行或探索",
        environment=["park", "outdoor"],
        concepts=["outing", "travel"],
    )

    assert brief.scene == "outing"
    assert brief.primary_action == "散步、旅行或探索"
    assert "excited" not in brief.required_concepts
    assert "兴奋" not in brief.required_concepts
    assert {"valentine", "medical", "wheelchair"}.issubset(brief.excluded_concepts)


def test_cat_visual_brief_is_schema_valid_and_specific():
    brief = _test_brief(
        "今天猫猫一直趴在键盘上不让我工作，最后只好抱着它一起看电影。虽然很平凡，但感觉被治愈了。",
        "开心",
        scene="home",
        sub_scene="pet_companion",
        subject="猫咪",
        action="陪伴",
        environment=["home"],
        objects=["cat"],
        concepts=["cat", "pet", "companion"],
        title="被猫治愈的一天",
    )

    assert brief.scene == "home"
    assert brief.sub_scene == "pet_companion"
    assert "cat" in brief.required_concepts
    assert brief.content_length == "medium"


def test_focal_candidate_requires_subject_action_or_required_concept():
    brief = _test_brief(
        "今天要出门去玩咯！！！你说应该去哪里玩呢",
        "兴奋",
        scene="outing",
        sub_scene="weekend_leisure",
        action="travel",
        concepts=["outing", "travel"],
    )
    unrelated = candidate(
        "flower",
        MaterialRole.FOCAL_STICKER,
        subjects=["flower"],
        actions=[],
        scenes=["garden"],
        objects=["bouquet"],
    ).model_dump(mode="json")

    reviewed, reason = score_candidate(unrelated, brief=brief, role=MaterialRole.FOCAL_STICKER)

    assert reviewed is None
    assert reason == "missing_subject_action_or_required_concept"


def test_excluded_concepts_and_text_heavy_are_hard_filtered():
    brief = _test_brief(
        "今天要出门去玩咯",
        "兴奋",
        scene="outing",
        sub_scene="weekend_leisure",
        concepts=["outing", "travel"],
    )
    risky = candidate(
        "valentine",
        MaterialRole.FOCAL_STICKER,
        subjects=["traveler"],
        actions=["travel"],
        scenes=["outing"],
        risk_flags=["valentine"],
        detected_text="HAPPY VALENTINE'S DAY",
        text_heavy=True,
    ).model_dump(mode="json")

    reviewed, reason = score_candidate(risky, brief=brief, role=MaterialRole.FOCAL_STICKER)

    assert reviewed is None
    assert reason == "excluded_concept:valentine"


def test_role_groups_are_not_flattened_or_reassigned():
    brief = _test_brief("今天和猫猫一起看电影", "开心", scene="home", sub_scene="pet_companion", concepts=["cat"])
    tape = candidate("tape", MaterialRole.TAPE)
    frame = candidate("frame", MaterialRole.FRAME)
    reviewed = review_material_role_groups(
        brief=brief,
        role_groups={"tape": [tape.model_dump(mode="json")], "frame": [frame.model_dump(mode="json")]},
    )

    assert reviewed["role_groups"]["tape"][0]["role"] == "tape"
    assert reviewed["role_groups"]["frame"][0]["role"] == "frame"


def test_template_binder_requires_exact_roles_and_resolver_falls_back():
    brief = _test_brief("今天和猫猫一起看电影", "开心", scene="home", sub_scene="pet_companion", concepts=["cat"])
    focal = candidate("cat", MaterialRole.FOCAL_STICKER, subjects=["cat"], actions=["companion"], scenes=["home"])
    center_tape = get_template("watermark_center_tape")
    bound = bind_materials_for_template(
        template=center_tape,
        visual_brief=brief,
        role_groups={"focal_sticker": [focal.model_dump(mode="json")]},
    )

    assert bound["satisfies_required_roles"] is False
    assert set(bound["missing_roles"]) == {"background", "tape"}
    plans = resolve_layout_plans(
        brief,
        [center_tape, get_template("short_note_focal_center"), get_template("minimal_text_only")],
        {"focal_sticker": [focal.model_dump(mode="json")]},
    )
    assert plans[0].template_id == "short_note_focal_center"


def test_step5_prefers_close_contextual_background_plan_with_same_focal():
    brief = _test_brief(
        "早上赶地铁，终于坐下来喝了一杯热豆浆。",
        "放松",
        scene="daily_life",
        sub_scene="commuting",
        environment=["地铁站", "站台"],
        concepts=["地铁", "豆浆"],
    )
    focal = candidate("commute-car", MaterialRole.FOCAL_STICKER, subjects=["汽车"], scenes=["通勤"])
    background = candidate(
        "subway-bg",
        MaterialRole.BACKGROUND,
        scenes=["地铁", "车厢内"],
    ).model_copy(
        update={
            "semantic_score": 0.58,
            "total_score": 0.58,
            "match_reasons": ["scene:地铁", "plan:query:地铁"],
        }
    )
    selected = LayoutPlan(
        template_id="short_note_focal_center",
        materials={"focal_sticker": focal},
        title="一杯热豆浆的治愈",
        score=0.858,
    )
    background_plan = LayoutPlan(
        template_id="watermark_center_clean",
        materials={"background": background, "focal_sticker": focal},
        title=selected.title,
        score=0.7486,
    )

    upgraded = step5_layout._prefer_contextual_background(selected, [selected, background_plan], brief)

    assert upgraded.template_id == "watermark_center_clean"
    assert upgraded.title == selected.title


def test_step5_does_not_force_irrelevant_or_materially_weaker_background():
    brief = _test_brief("今天只是随手记了几句话。", "平静")
    focal = candidate("note", MaterialRole.FOCAL_STICKER, subjects=["日记"])
    selected = LayoutPlan(
        template_id="short_note_focal_center",
        materials={"focal_sticker": focal},
        title="今天的一页",
        score=0.86,
    )
    irrelevant_background = candidate("generic-bg", MaterialRole.BACKGROUND).model_copy(
        update={"match_reasons": ["role:background"]}
    )
    weak_background = candidate("weak-bg", MaterialRole.BACKGROUND, scenes=["daily_life"]).model_copy(
        update={"match_reasons": ["scene:daily_life"]}
    )
    irrelevant_plan = LayoutPlan(
        template_id="watermark_center_clean",
        materials={"background": irrelevant_background, "focal_sticker": focal},
        title=selected.title,
        score=0.82,
    )
    weak_plan = LayoutPlan(
        template_id="watermark_left_focal",
        materials={"background": weak_background, "focal_sticker": focal},
        title=selected.title,
        score=0.70,
    )

    kept = step5_layout._prefer_contextual_background(
        selected,
        [selected, irrelevant_plan, weak_plan],
        brief,
    )

    assert kept.template_id == "short_note_focal_center"


def test_compiler_is_deterministic_and_validator_is_read_only():
    text = "今天猫猫一直趴在键盘上不让我工作，最后抱着它一起看电影。"
    brief = _test_brief(text, "开心", scene="home", sub_scene="pet_companion", concepts=["cat", "companion"])
    materials = {
        "background": candidate("home-bg", MaterialRole.BACKGROUND, scenes=["home"]),
        "focal_sticker": candidate("cat", MaterialRole.FOCAL_STICKER, subjects=["cat"], actions=["companion"], scenes=["home"]),
        "tape": candidate("flower-tape", MaterialRole.TAPE),
    }
    plan = LayoutPlan(template_id="watermark_center_tape", materials=materials, title="被猫治愈的一天", score=0.9)
    kwargs = {
        "plan": plan,
        "visual_brief": brief,
        "authoritative_context": authoritative_context(),
        "mood": "开心",
        "task_id": "v2-cat",
        "content_text": text,
    }

    first = compile_layout_v2(**kwargs)
    second = compile_layout_v2(**kwargs)
    before = deepcopy(first)
    errors = validate_layout_v2(first, plan=plan, authoritative_context=authoritative_context())

    assert first == second
    assert first == before
    assert errors == []
    assert first["meta"]["layout_engine"] == "v2"
    assert {element["props"].get("role") for element in first["elements"] if element["type"] in {"image", "sticker", "decoration"}} == {
        "background",
        "focal_sticker",
        "tape",
    }
    body = next(element for element in first["elements"] if element.get("props", {}).get("role") == "body")
    assert body["props"]["content"] == text


def test_compiler_non_text_geometry_is_stable_across_ten_runs():
    text = "今天猫猫陪我看了一场电影。"
    brief = _test_brief(text, "开心", scene="home", sub_scene="pet_companion", concepts=["cat", "companion"])
    plan = LayoutPlan(
        template_id="watermark_center_tape",
        materials={
            "background": candidate("home-bg", MaterialRole.BACKGROUND, scenes=["home"]),
            "focal_sticker": candidate("cat", MaterialRole.FOCAL_STICKER, subjects=["cat"], scenes=["home"]),
            "tape": candidate("tape", MaterialRole.TAPE),
        },
        title="被猫治愈的一天",
        score=0.9,
    )

    layouts = [
        compile_layout_v2(
            plan=plan,
            visual_brief=brief,
            authoritative_context=authoritative_context(),
            mood="开心",
            task_id="stable",
            content_text=text,
        )
        for _ in range(10)
    ]
    geometry = [
        [
            (element["type"], element["props"].get("role"), element["props"].get("x"), element["props"].get("y"), element["props"].get("w"), element["props"].get("h"), element["z_index"])
            for element in layout["elements"]
            if element["type"] not in {"text", "date_tag", "mood_tag", "weather_tag"}
        ]
        for layout in layouts
    ]

    assert all(item == geometry[0] for item in geometry[1:])


def test_v1_sticker_role_compatibility_uses_usage_type_without_overriding_explicit_role():
    legacy_focal = SimpleNamespace(
        material_type="sticker",
        scene_tags=[],
        style_tags=[],
        meta_info={"usage_type": "主体贴图"},
    )
    explicit_supporting = SimpleNamespace(
        material_type="sticker",
        scene_tags=[],
        style_tags=[],
        meta_info={"usage_type": "主体贴图", "suggested_role": "supporting_sticker"},
    )

    assert normalize_material_metadata(legacy_focal).suggested_role is MaterialRole.FOCAL_STICKER
    assert normalize_material_metadata(explicit_supporting).suggested_role is MaterialRole.SUPPORTING_STICKER


def test_long_content_filters_to_text_forward_templates():
    brief = _test_brief("这是一段需要完整记录的长正文。" * 20, "平静")
    templates = filter_templates(brief)

    assert templates[0]["layout_type"] == "text_forward"
    assert brief.content_length == "long"


def test_visual_bbox_uses_alpha_subject_bounds():
    image = Image.new("RGBA", (100, 100), (255, 255, 255, 0))
    ImageDraw.Draw(image).rectangle((20, 25, 79, 84), fill=(80, 50, 30, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    bbox = calculate_visual_bbox(buffer.getvalue())

    assert bbox.x == pytest.approx(0.2)
    assert bbox.y == pytest.approx(0.25)
    assert bbox.w == pytest.approx(0.6)
    assert bbox.h == pytest.approx(0.6)


def test_visual_bbox_falls_back_to_full_image_for_svg_or_invalid_bytes():
    assert calculate_visual_bbox(b"<svg/>", mime_type="image/svg+xml").model_dump() == {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
    assert calculate_visual_bbox(b"not-an-image").model_dump() == {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}


def test_backfill_normalizes_model_enums_and_batch_labels():
    payload = normalize_visual_payload(
        {
            "complexity": "中等",
            "density": "低密度",
            "text_heavy": "否",
            "background_safe": "是",
            "suggested_role": "主体贴图",
            "risk_flags": ["party", "未知风险"],
        }
    )
    parsed = parse_batch_json('{"items":[{"label":"A01","complexity":"low"}]}')

    assert payload["complexity"] == "medium"
    assert payload["density"] == "low"
    assert payload["text_heavy"] is False
    assert payload["background_safe"] is True
    assert payload["suggested_role"] == "focal_sticker"
    assert payload["risk_flags"] == ["party"]
    assert parsed["A01"]["complexity"] == "low"


def test_backfill_parses_first_json_object_from_local_model_explanation():
    parsed = parse_batch_json(
        '分析结果如下：```json\n{"items":[{"label":"A01","density":"低"}]}\n``` 后续说明 {"ignored":true}'
    )

    assert parsed["A01"]["density"] == "低"


def test_compiler_layout_is_json_serializable():
    brief = _test_brief("短短的一句话", "平静")
    plan = LayoutPlan(template_id="minimal_text_only", materials={}, title="今天的一页", score=0.2)
    layout = compile_layout_v2(
        plan=plan,
        visual_brief=brief,
        authoritative_context=authoritative_context(),
        mood="平静",
        task_id="minimal",
        content_text="短短的一句话",
    )

    assert json.loads(json.dumps(layout, ensure_ascii=False))["meta"]["template_id"] == "minimal_text_only"


@pytest.mark.asyncio
async def test_step5_v2_model_failure_uses_highest_scored_legal_plan(monkeypatch):
    async def fail_model(*_args, **_kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(step5_layout, "_call_layout_model", fail_model)
    text = "今天猫猫趴在键盘上，最后抱着它一起看电影。"
    brief = _test_brief(text, "开心", scene="home", sub_scene="pet_companion", concepts=["cat", "companion"])
    background = candidate("home-bg", MaterialRole.BACKGROUND, scenes=["home"])
    focal = candidate("cat", MaterialRole.FOCAL_STICKER, subjects=["cat"], actions=["companion"], scenes=["home"])
    tape = candidate("tape", MaterialRole.TAPE)
    ctx = {
        "task_id": "step5-v2",
        "input_json": {"text": text, "mood": "开心"},
        "visual_brief": brief.model_dump(mode="json"),
        "step4_review": {
            "summary": {
                "template_candidates": [
                    {"id": "watermark_center_tape"},
                    {"id": "minimal_text_only"},
                ]
            },
            "role_groups": {
                "background": [background.model_dump(mode="json")],
                "focal_sticker": [focal.model_dump(mode="json")],
                "tape": [tape.model_dump(mode="json")],
            },
        },
        "journal_context": {
            "weather_success": True,
            "datetime": {"date": "2026-06-20", "weekday": "周六"},
            "journal_header": {"date_text": "2026.06.20 周六", "weather_text": "多云", "weather_icon": "⛅"},
            "weather": {"text": "多云", "icon": "⛅", "icon_key": "cloudy"},
        },
    }

    layout = json.loads(await step5_layout.run_layout_generation(ctx))

    assert layout["meta"]["layout_engine"] == "v2"
    assert layout["meta"]["template_id"] == "watermark_center_tape"
    assert ctx["layout_v2_plan"]["template_id"] == "watermark_center_tape"


@pytest.mark.asyncio
async def test_step6_v2_uses_fallback_template_without_repairing_geometry(monkeypatch):
    text = "今天猫猫趴在键盘上。"
    brief = _test_brief(text, "开心", scene="home", sub_scene="pet_companion", concepts=["cat", "companion"])
    background = candidate("home-bg", MaterialRole.BACKGROUND, scenes=["home"])
    focal = candidate("cat", MaterialRole.FOCAL_STICKER, subjects=["cat"], actions=["companion"], scenes=["home"])
    tape = candidate("tape", MaterialRole.TAPE)
    plan = LayoutPlan(
        template_id="watermark_center_tape",
        materials={"background": background, "focal_sticker": focal, "tape": tape},
        title="被猫治愈的一天",
        score=0.9,
    )
    context = authoritative_context()
    layout = compile_layout_v2(
        plan=plan,
        visual_brief=brief,
        authoritative_context=context,
        mood="开心",
        task_id="step6-v2",
        content_text=text,
    )
    focal_element = next(item for item in layout["elements"] if item.get("props", {}).get("role") == "focal_sticker")
    focal_element["props"]["x"] = -10
    ctx = {
        "task_id": "step6-v2",
        "input_json": {"text": text, "mood": "开心"},
        "visual_brief": brief.model_dump(mode="json"),
        "layout_v2_plan": plan.model_dump(mode="json"),
        "layout_v2_authoritative_context": context,
        "step5": json.dumps(layout, ensure_ascii=False),
        "step4_review": {
            "role_groups": {
                "background": [background.model_dump(mode="json")],
                "focal_sticker": [focal.model_dump(mode="json")],
                "tape": [tape.model_dump(mode="json")],
            }
        },
    }

    fallback = await run_validate_and_repair(ctx)

    assert fallback["meta"]["template_id"] == "watermark_center_clean"
    assert not any(item.get("props", {}).get("role") == "tape" for item in fallback["elements"])
    expected = compile_layout_v2(
        plan=LayoutPlan(
            template_id="watermark_center_clean",
            materials={"background": background, "focal_sticker": focal},
            title=plan.title,
            score=0,
        ),
        visual_brief=brief,
        authoritative_context=context,
        mood="开心",
        task_id="step6-v2",
        content_text=text,
    )
    assert fallback["elements"] == expected["elements"]


@pytest.mark.asyncio
async def test_v2_pipeline_preserves_role_groups_through_compile_and_validation(monkeypatch):
    text = "今天猫猫趴在键盘上，最后抱着它一起看电影。"
    brief = _test_brief(text, "开心", scene="home", sub_scene="pet_companion", concepts=["cat", "companion"])
    materials = {
        "background": candidate("home-bg", MaterialRole.BACKGROUND, scenes=["home"]),
        "focal_sticker": candidate("cat", MaterialRole.FOCAL_STICKER, subjects=["cat"], actions=["companion"], scenes=["home"]),
        "tape": candidate("tape", MaterialRole.TAPE),
    }

    async def retrieve(**_kwargs):
        return {
            "role_groups": {role: [item.model_dump(mode="json")] for role, item in materials.items()},
            "rejected": [],
        }

    async def fail_model(*_args, **_kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.ai.layout_v2.material_retriever.retrieve_material_role_groups", retrieve)
    monkeypatch.setattr(step5_layout, "_call_layout_model", fail_model)
    ctx = {
        "task_id": "pipeline-v2",
        "user_id": None,
        "input_json": {"text": text, "mood": "开心"},
        "visual_brief": brief.model_dump(mode="json"),
        "journal_context": {
            "weather_success": True,
            "datetime": {"date": "2026-06-20", "weekday": "周六"},
            "journal_header": {"date_text": "2026.06.20 周六", "weather_text": "多云", "weather_icon": "⛅"},
            "weather": {"text": "多云", "icon": "⛅", "icon_key": "cloudy"},
        },
    }

    ctx["step4"] = await run_material_matching(ctx)
    ctx["step4_review"] = await run_material_review(ctx)
    ctx["step5"] = await step5_layout.run_layout_generation(ctx)
    layout = await run_validate_and_repair(ctx)

    assert layout["meta"]["layout_engine"] == "v2"
    assert layout["meta"]["template_id"] == "watermark_center_tape"
    assert {item["props"].get("role") for item in layout["elements"] if item["type"] in {"image", "sticker", "decoration"}} == set(materials)
    assert set(ctx["step4_review"]["role_groups"]) >= set(materials)
