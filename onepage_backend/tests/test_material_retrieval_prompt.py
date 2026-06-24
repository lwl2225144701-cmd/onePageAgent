from __future__ import annotations

import json

import httpx
import pytest

from app.ai.gateway.local_ollama_text_client import LocalOllamaTextClient, LocalOllamaTextError
from app.ai.layout_v2.material_plan_cache import build_material_plan_cache_key
from app.ai.layout_v2 import material_retrieval_planner
from app.ai.layout_v2.material_retrieval_plan import (
    MaterialRetrievalPlan,
    MaterialRetrievalWhitelist,
    normalize_material_retrieval_plan,
)
from app.ai.prompt_registry import (
    MATERIAL_RETRIEVAL_FEWSHOTS,
    MATERIAL_RETRIEVAL_SYSTEM_PROMPT,
    build_material_retrieval_prompt,
    parse_material_retrieval_plan,
    select_material_retrieval_fewshots,
)
from app.ai.layout_v2.material_retriever import score_candidate
from app.ai.layout_v2.material_sql_compiler import compile_material_plan_to_sql
from app.ai.layout_v2.enums import MaterialRole
from app.ai.layout_v2.schemas import VisualBrief


def whitelist() -> MaterialRetrievalWhitelist:
    return MaterialRetrievalWhitelist(
        categories=[
            "食物饮品",
            "动物生物",
            "人物角色",
            "交通建筑",
            "学习办公",
            "通用背景",
            "场景背景",
            "自然风景",
            "其他拼贴",
        ],
        sub_categories=[
            "主食料理",
            "饮料酒水",
            "甜品零食",
            "宠物",
            "人物动作",
            "交通工具",
            "文具书籍",
            "考试学习",
            "通用",
            "其他",
        ],
        styles=["日系", "可爱", "极简", "水彩", "装饰"],
    )


def brief(scene: str = "food", sub_scene: str = "food_review", length: str = "short") -> VisualBrief:
    return VisualBrief(
        topic="今天的一页",
        scene=scene,
        sub_scene=sub_scene,
        content_length=length,
        required_concepts=["food", "meal"] if scene == "food" else [],
        visual_keywords=["food"] if scene == "food" else [],
    )


def normalized_food_plan() -> MaterialRetrievalPlan:
    return normalize_material_retrieval_plan(
        {
            "scene": "food",
            "sub_scene": "food_review",
            "strategy": "progressive",
            "groups": [
                {
                    "role": "focal_sticker",
                    "categories": ["食物饮品"],
                    "sub_categories": ["主食料理"],
                    "query_terms": ["桂林米粉", "米粉", "面食"],
                    "styles": ["日系"],
                }
            ],
        },
        visual_brief=brief(),
        whitelist=whitelist(),
    )


def test_fewshot_selector_returns_only_relevant_two_or_three():
    selected = select_material_retrieval_fewshots(
        visual_brief=brief(),
        user_text="今天吃了桂林米粉",
        limit=2,
    )

    assert len(selected) == 2
    assert selected[0]["name"] == "food_noodle"
    assert all(item in MATERIAL_RETRIEVAL_FEWSHOTS for item in selected)
    selected_with_maximum = select_material_retrieval_fewshots(
        visual_brief=brief(),
        user_text="米粉",
        limit=99,
    )
    assert 2 <= len(selected_with_maximum) <= 3
    assert all(item["name"] != "pet_home" for item in selected_with_maximum)


def test_fewshot_selector_uses_minimal_example_instead_of_unrelated_scene():
    selected = select_material_retrieval_fewshots(
        visual_brief=brief(scene="home", sub_scene="pet_companion", length="medium"),
        user_text="猫咪陪我看电影",
        limit=2,
    )

    assert [item["name"] for item in selected] == ["pet_home", "quiet_minimal"]


def test_fewshot_selector_uses_ai_brief_not_raw_text_keyword_override():
    selected = select_material_retrieval_fewshots(
        visual_brief=VisualBrief(
            scene="study",
            sub_scene="study_record",
            content_length="short",
            objects=["笔记", "试卷"],
            required_concepts=["study", "exam"],
            visual_keywords=["学习", "复习"],
        ),
        user_text="文中顺带提到昨天吃过桂林米粉",
        limit=2,
    )

    assert selected[0]["name"] == "study_notes"
    assert selected[0]["name"] != "food_noodle"


def test_prompt_is_compact_and_contains_only_selected_fewshots():
    prompt = build_material_retrieval_prompt(
        user_text="今天吃了桂林米粉",
        mood="开心",
        weather="晴",
        visual_brief=brief(),
        allowed_roles=whitelist().roles,
        allowed_categories=whitelist().categories,
        allowed_sub_categories=whitelist().sub_categories,
        allowed_styles=whitelist().styles,
        fewshot_limit=2,
    )
    payload = json.loads(prompt)

    assert len(prompt) < 5000
    assert len(payload["fewshots"]) == 2
    assert payload["fewshots"][0]["output"]["groups"][0]["categories"] == ["食物饮品"]
    assert "exclude_risks" not in payload["fewshots"][0]["output"]["groups"][0]
    assert "不能输出 SQL" in MATERIAL_RETRIEVAL_SYSTEM_PROMPT


def test_parse_plan_extracts_first_json_object_from_markdown():
    parsed = parse_material_retrieval_plan(
        '结果如下```json\n{"scene":"food","groups":[]}\n```后续说明 {"ignored":true}'
    )

    assert parsed == {"scene": "food", "groups": []}


def test_normalize_drops_unknown_values_and_adds_backend_defaults():
    plan = normalize_material_retrieval_plan(
        {
            "scene": "food",
            "sub_scene": "food_review",
            "strategy": "progressive",
            "sql": "DELETE FROM materials",
            "groups": [
                {
                    "role": "focal_sticker",
                    "categories": ["食物饮品", "美食评价"],
                    "sub_categories": ["主食料理", "米粉料理"],
                    "query_terms": ["桂林米粉", "面食"],
                    "styles": ["日系", "高级感"],
                    "material_id": "forbidden",
                }
            ],
        },
        visual_brief=brief(),
        whitelist=whitelist(),
    )
    group = plan.groups[0]

    assert group.categories == ["食物饮品"]
    assert group.sub_categories == ["主食料理"]
    assert group.styles == ["日系"]
    assert group.material_types == ["sticker"]
    assert group.suggested_roles == ["focal_sticker"]
    assert group.limit == 20
    assert group.density == ["low", "medium"]
    assert group.background_safe is False
    assert "party" in group.exclude_risks
    assert "sql" not in plan.model_dump()


def test_empty_model_groups_use_safe_minimal_fallback():
    plan = normalize_material_retrieval_plan({}, visual_brief=brief(), whitelist=whitelist())

    assert plan.source == "fallback"
    assert plan.strategy == "minimal"
    assert plan.groups == []


def test_long_text_fallback_does_not_add_materials():
    plan = normalize_material_retrieval_plan(
        {},
        visual_brief=brief(scene="daily_life", sub_scene="long_text", length="long"),
        whitelist=whitelist(),
    )

    assert plan.strategy == "minimal"
    assert plan.groups == []


def test_fallback_does_not_guess_category_from_scene_name():
    plan = normalize_material_retrieval_plan(
        {},
        visual_brief=brief(scene="home", sub_scene="pet_companion", length="medium"),
        whitelist=whitelist(),
    )

    assert plan.strategy == "minimal"
    assert plan.groups == []


def test_outing_fallback_does_not_guess_people_or_transport_categories():
    plan = normalize_material_retrieval_plan(
        {},
        visual_brief=brief(scene="outing", sub_scene="weekend_leisure", length="short"),
        whitelist=whitelist(),
    )

    assert plan.strategy == "minimal"
    assert plan.groups == []


def test_sql_compiler_uses_bound_params_and_never_embeds_user_terms():
    group = normalized_food_plan().groups[0]
    statement, params = compile_material_plan_to_sql(group, "user-1")
    sql = str(statement)

    assert "桂林米粉" not in sql
    assert "DELETE" not in sql
    assert ":query_terms_json" in sql
    assert ":exclude_risks_json" in sql
    assert json.loads(params["query_terms_json"])[0] == "桂林米粉"
    assert params["user_id"] == "user-1"


def test_plan_category_signal_allows_food_candidate_to_pass_existing_score():
    group = normalized_food_plan().groups[0]
    candidate, reason = score_candidate(
        {
            "material_id": "food-1",
            "role": "focal_sticker",
            "file_url": "https://example.com/food.png",
            "category": "食物饮品",
            "sub_category": "主食料理",
            "display_name": "一碗面食",
            "metadata": {
                "suggested_role": "focal_sticker",
                "subjects": [],
                "actions": [],
                "scenes": [],
                "objects": [],
                "density": "low",
                "complexity": "low",
                "annotation_version": "v2",
            },
        },
        brief=brief(),
        role=MaterialRole.FOCAL_STICKER,
        retrieval_group=group,
    )

    assert reason == ""
    assert candidate is not None
    assert candidate.semantic_score >= 0.55
    assert "plan:category:食物饮品" in candidate.match_reasons


def test_broad_category_alone_does_not_fill_supporting_sticker_with_random_material():
    plan = normalize_material_retrieval_plan(
        {
            "groups": [
                {
                    "role": "supporting_sticker",
                    "categories": ["人物角色"],
                    "query_terms": ["点赞"],
                }
            ]
        },
        visual_brief=brief(),
        whitelist=whitelist(),
    )
    candidate, reason = score_candidate(
        {
            "material_id": "unrelated-1",
            "role": "supporting_sticker",
            "file_url": "https://example.com/unrelated.png",
            "category": "人物角色",
            "sub_category": "人物动作",
            "display_name": "正在跑步的人",
            "metadata": {
                "suggested_role": "supporting_sticker",
                "density": "low",
                "complexity": "low",
                "annotation_version": "v2",
            },
        },
        brief=brief(),
        role=MaterialRole.SUPPORTING_STICKER,
        retrieval_group=plan.groups[0],
    )

    assert candidate is None
    assert reason == "weak_retrieval_plan_match"


def test_cache_key_changes_with_prompt_inputs_and_taxonomy():
    first = build_material_plan_cache_key(
        visual_brief=brief(),
        whitelist=whitelist(),
        mood="开心",
        weather="晴",
    )
    second = build_material_plan_cache_key(
        visual_brief=brief(),
        whitelist=whitelist().model_copy(update={"categories": ["通用背景"]}),
        mood="开心",
        weather="晴",
    )

    assert first.startswith("onepage:material-plan:")
    assert first != second


@pytest.mark.asyncio
async def test_local_text_client_uses_json_mode_and_small_output_budget():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"groups":[]}'}, "eval_count": 10})

    client = LocalOllamaTextClient()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await client.generate_json(prompt="{}", system_prompt="只输出 JSON", task_id="test")

    assert captured["format"] == "json"
    assert captured["stream"] is False
    assert captured["keep_alive"] == "30m"
    assert captured["options"] == {"temperature": 0.1, "num_predict": 220}
    assert result["content"] == '{"groups":[]}'
    await client.close()


@pytest.mark.asyncio
async def test_local_text_client_reports_connection_errors():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = LocalOllamaTextClient()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    with pytest.raises(LocalOllamaTextError, match="local_text_llm_connection_error"):
        await client.generate_json(prompt="{}", system_prompt="JSON")
    await client.close()


@pytest.mark.asyncio
async def test_planner_cache_hit_does_not_call_local_model(monkeypatch):
    cached = normalized_food_plan().model_copy(update={"source": "cache"})

    async def fake_cache(**_kwargs):
        return cached

    async def fail_generate(*_args, **_kwargs):
        raise AssertionError("local model must not run on cache hit")

    monkeypatch.setattr(material_retrieval_planner, "get_cached_material_plan", fake_cache)
    monkeypatch.setattr(LocalOllamaTextClient, "generate_json", fail_generate)

    plan = await material_retrieval_planner.create_material_retrieval_plan(
        visual_brief=brief(),
        user_text="今天吃了桂林米粉",
        mood="开心",
        weather="晴",
        whitelist=whitelist(),
        task_id="cache-test",
    )

    assert plan.source == "cache"
    assert plan.groups[0].categories == ["食物饮品"]


@pytest.mark.asyncio
async def test_planner_model_failure_uses_safe_minimal_fallback(monkeypatch):
    async def fake_cache(**_kwargs):
        return None

    async def fail_generate(*_args, **_kwargs):
        raise LocalOllamaTextError("local_text_llm_timeout")

    monkeypatch.setattr(material_retrieval_planner, "get_cached_material_plan", fake_cache)
    monkeypatch.setattr(LocalOllamaTextClient, "generate_json", fail_generate)

    plan = await material_retrieval_planner.create_material_retrieval_plan(
        visual_brief=brief(),
        user_text="今天吃了桂林米粉",
        mood="开心",
        weather="晴",
        whitelist=whitelist(),
        task_id="fallback-test",
    )

    assert plan.source == "fallback"
    assert plan.strategy == "minimal"
    assert plan.groups == []
