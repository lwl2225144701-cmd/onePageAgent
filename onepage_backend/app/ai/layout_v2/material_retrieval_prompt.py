from __future__ import annotations

import json
from typing import Any

from app.ai.layout_v2.schemas import VisualBrief


MATERIAL_RETRIEVAL_PROMPT_VERSION = "v2-minimal-2"

MATERIAL_RETRIEVAL_SYSTEM_PROMPT = """你是 onePage 手帐素材召回规划器。
根据用户内容、心情、天气和 VisualBrief，输出最小素材召回计划。
role、category、sub_category、style 只能从输入白名单选择。
不能输出 SQL、素材 ID、URL、坐标、默认参数或解释。
精确物品只放入 query_terms 用于排序，不作为唯一召回条件；找不到时退让到大类。
情绪只影响风格，不决定主体素材。长正文减少主贴纸；不可靠时使用 minimal。
最多输出 3 个 group。只输出紧凑 JSON。"""


MATERIAL_RETRIEVAL_FEWSHOTS: list[dict[str, Any]] = [
    {
        "name": "food_noodle",
        "scenes": ["food", "daily_life"],
        "sub_scenes": ["food_review", "food_record"],
        "content_lengths": ["short", "medium"],
        "keywords": ["米粉", "面食", "主食", "好吃"],
        "input": "今天吃了桂林米粉，真的好香。",
        "output": {
            "scene": "food",
            "sub_scene": "food_review",
            "strategy": "progressive",
            "groups": [
                {
                    "role": "focal_sticker",
                    "categories": ["食物饮品"],
                    "sub_categories": ["主食料理"],
                    "query_terms": ["桂林米粉", "米粉", "面食", "主食"],
                    "styles": ["日系", "可爱"],
                },
                {
                    "role": "background",
                    "categories": ["通用背景"],
                    "sub_categories": ["通用"],
                    "query_terms": ["暖色", "纸张", "低饱和"],
                    "styles": ["日系", "极简"],
                },
            ],
        },
    },
    {
        "name": "food_coffee",
        "scenes": ["food", "daily_life"],
        "sub_scenes": ["cafe_record", "food_review"],
        "content_lengths": ["short", "medium"],
        "keywords": ["咖啡", "拿铁", "咖啡店", "下午茶"],
        "input": "下午去了咖啡店，点了一杯拿铁。",
        "output": {
            "scene": "food",
            "sub_scene": "cafe_record",
            "strategy": "progressive",
            "groups": [
                {
                    "role": "focal_sticker",
                    "categories": ["食物饮品"],
                    "sub_categories": ["饮料酒水", "甜品零食"],
                    "query_terms": ["咖啡", "拿铁", "饮料", "下午茶"],
                    "styles": ["日系", "可爱"],
                },
                {
                    "role": "background",
                    "categories": ["通用背景", "场景背景"],
                    "sub_categories": ["通用"],
                    "query_terms": ["窗边", "放松", "暖色"],
                    "styles": ["日系", "极简"],
                },
            ],
        },
    },
    {
        "name": "pet_home",
        "scenes": ["home", "pet"],
        "sub_scenes": ["pet_companion"],
        "content_lengths": ["short", "medium"],
        "keywords": ["猫", "猫咪", "宠物", "陪伴"],
        "input": "今天猫猫趴在键盘上，最后抱着它一起看电影。",
        "output": {
            "scene": "home",
            "sub_scene": "pet_companion",
            "strategy": "progressive",
            "groups": [
                {
                    "role": "focal_sticker",
                    "categories": ["动物生物"],
                    "sub_categories": ["宠物"],
                    "query_terms": ["猫", "猫咪", "宠物", "陪伴"],
                    "styles": ["可爱", "日系"],
                },
                {
                    "role": "background",
                    "categories": ["通用背景", "场景背景"],
                    "sub_categories": ["通用"],
                    "query_terms": ["居家", "治愈", "安静"],
                    "styles": ["日系", "极简"],
                },
            ],
        },
    },
    {
        "name": "outing_travel",
        "scenes": ["outing", "travel"],
        "sub_scenes": ["weekend_leisure", "travel_memory"],
        "content_lengths": ["short", "medium"],
        "keywords": ["出门", "游玩", "旅行", "散步", "公园"],
        "input": "今天要出门去玩，你说应该去哪里呢？",
        "output": {
            "scene": "outing",
            "sub_scene": "weekend_leisure",
            "strategy": "progressive",
            "groups": [
                {
                    "role": "focal_sticker",
                    "categories": ["人物角色", "交通建筑"],
                    "sub_categories": ["人物动作", "交通工具"],
                    "query_terms": ["出门", "游玩", "散步", "旅行"],
                    "styles": ["日系", "可爱"],
                },
                {
                    "role": "background",
                    "categories": ["自然风景", "场景背景"],
                    "sub_categories": ["通用"],
                    "query_terms": ["户外", "公园", "街道", "清新"],
                    "styles": ["日系", "水彩"],
                },
            ],
        },
    },
    {
        "name": "study_notes",
        "scenes": ["study", "reading"],
        "sub_scenes": ["study_record", "study_reflection", "quiet_reading"],
        "content_lengths": ["short", "medium"],
        "keywords": ["学习", "复习", "笔记", "错题", "阅读"],
        "input": "晚上复习了两个小时，把错题整理完了。",
        "output": {
            "scene": "study",
            "sub_scene": "study_record",
            "strategy": "progressive",
            "groups": [
                {
                    "role": "focal_sticker",
                    "categories": ["学习办公"],
                    "sub_categories": ["文具书籍", "考试学习"],
                    "query_terms": ["学习", "复习", "错题", "笔记", "书本"],
                    "styles": ["日系", "极简"],
                },
                {
                    "role": "background",
                    "categories": ["通用背景"],
                    "sub_categories": ["通用"],
                    "query_terms": ["纸张", "安静", "学习"],
                    "styles": ["极简", "日系"],
                },
            ],
        },
    },
    {
        "name": "long_text",
        "scenes": ["daily_life", "work", "self_growth"],
        "sub_scenes": ["long_text"],
        "content_lengths": ["long"],
        "keywords": ["认真记录", "最近状态", "慢慢", "生活"],
        "input": "今天想认真记录一下最近的状态，慢慢写下生活中的变化。",
        "output": {
            "scene": "daily_life",
            "sub_scene": "long_text",
            "strategy": "minimal",
            "groups": [
                {
                    "role": "background",
                    "categories": ["通用背景"],
                    "sub_categories": ["通用"],
                    "query_terms": ["纸张", "留白", "低密度", "日记"],
                    "styles": ["极简", "日系"],
                }
            ],
        },
    },
    {
        "name": "quiet_minimal",
        "scenes": ["daily_life", "minimal"],
        "sub_scenes": ["quiet_mood", "general_daily"],
        "content_lengths": ["short", "medium", "long"],
        "keywords": ["安静", "发呆", "脑子空", "低落"],
        "input": "今天脑子有点空，只想安静地待一会儿。",
        "output": {
            "scene": "daily_life",
            "sub_scene": "quiet_mood",
            "strategy": "minimal",
            "groups": [
                {
                    "role": "background",
                    "categories": ["通用背景"],
                    "sub_categories": ["通用"],
                    "query_terms": ["安静", "低饱和", "纸张", "留白"],
                    "styles": ["极简", "日系"],
                }
            ],
        },
    },
]


def select_material_retrieval_fewshots(
    *,
    visual_brief: VisualBrief,
    user_text: str,
    limit: int = 2,
) -> list[dict[str, Any]]:
    count = max(1, min(int(limit or 2), 3))
    lowered = str(user_text or "").lower()
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for index, fewshot in enumerate(MATERIAL_RETRIEVAL_FEWSHOTS):
        score = 0.0
        if visual_brief.sub_scene in fewshot["sub_scenes"]:
            score += 7.0
        if visual_brief.scene in fewshot["scenes"]:
            score += 5.0
        if visual_brief.content_length in fewshot["content_lengths"]:
            score += 2.0
        score += min(4.0, sum(1.0 for token in fewshot["keywords"] if token.lower() in lowered))
        scored.append((score, -index, fewshot))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = [item for item in scored if item[0] >= 5.0][:count]
    minimum = min(2, count)
    if len(selected) < minimum:
        minimal = next(item for item in scored if item[2]["name"] == "quiet_minimal")
        if all(item[2]["name"] != minimal[2]["name"] for item in selected):
            selected.append(minimal)
    if len(selected) < minimum:
        remaining = [item for item in scored if item not in selected]
        selected.extend(remaining[: minimum - len(selected)])
    return [item[2] for item in selected]


def build_material_retrieval_prompt(
    *,
    user_text: str,
    mood: str,
    weather: str,
    visual_brief: VisualBrief,
    allowed_roles: list[str],
    allowed_categories: list[str],
    allowed_sub_categories: list[str],
    allowed_styles: list[str],
    fewshot_limit: int = 2,
) -> str:
    fewshots = select_material_retrieval_fewshots(
        visual_brief=visual_brief,
        user_text=user_text,
        limit=fewshot_limit,
    )
    compact_fewshots = [{"input": item["input"], "output": item["output"]} for item in fewshots]
    payload = {
        "user_text": str(user_text or "").strip(),
        "mood": str(mood or "").strip(),
        "weather": str(weather or "unknown").strip(),
        "visual_brief": {
            "scene": visual_brief.scene,
            "sub_scene": visual_brief.sub_scene,
            "content_length": visual_brief.content_length,
            "required_concepts": visual_brief.required_concepts,
            "objects": visual_brief.objects,
            "preferred_color_tone": visual_brief.preferred_color_tone,
        },
        "allowed_roles": allowed_roles,
        "allowed_categories": allowed_categories,
        "allowed_sub_categories": allowed_sub_categories,
        "allowed_styles": allowed_styles,
        "fewshots": compact_fewshots,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def parse_material_retrieval_plan(raw: str) -> dict[str, Any]:
    text = str(raw or "").replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("material_retrieval_plan_json_missing")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                payload = json.loads(text[start : index + 1])
                if not isinstance(payload, dict):
                    raise ValueError("material_retrieval_plan_not_object")
                return payload
    raise ValueError("material_retrieval_plan_json_incomplete")
