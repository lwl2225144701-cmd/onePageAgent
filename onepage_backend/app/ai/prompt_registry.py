from __future__ import annotations

import json
from typing import Any

from app.ai.layout_v2.schemas import VisualBrief


UNIFIED_ANALYSIS_SYSTEM_PROMPT = """你是 onePage 手帐的内容分析器。
一次完成语义、情绪和视觉风格分析，并只输出 JSON。
场景与关键词必须来自用户真实内容，不得用情绪替代主体，不得虚构事件。
keywords、objects、required_concepts 应保留食物名、地点、人物、动物、物件等可用于素材检索的具体名词。
avoid_tags 用于排除与内容冲突的素材语义。
天气只影响视觉风格，不改变内容主体。
输出结构必须包含 semantic、sentiment、style 三个对象，不要输出解释。"""


def build_unified_analysis_prompt(
    *,
    user_text: str,
    mood: str,
    environment_context: dict[str, Any] | None,
    user_preferences: dict[str, Any] | None,
) -> str:
    payload = {
        "user_text": str(user_text or "").strip(),
        "user_mood": str(mood or "").strip(),
        "environment_context": environment_context if isinstance(environment_context, dict) else {},
        "user_preferences": user_preferences if isinstance(user_preferences, dict) else {},
        "output_schema": {
            "semantic": {
                "topic": "简短主题",
                "scene": "daily_life/home/pet/food/outing/travel/study/work/reading/exercise/emotion_record",
                "sub_scene": "更具体的英文场景",
                "intent": "用户记录意图",
                "primary_subject": "主要主体",
                "primary_action": "主要动作",
                "environment": ["场景环境词"],
                "objects": ["原文中的具体物体"],
                "keywords": ["原文中的检索关键词"],
                "visual_keywords": ["适合视觉检索的关键词"],
                "required_concepts": ["必须命中的主体概念"],
                "avoid_tags": ["必须排除的冲突语义"],
                "title_hint": "不超过20个汉字的自然标题",
            },
            "sentiment": {
                "primary_emotion": "happy/calm/excited/sad/anxious/nostalgic/neutral",
                "secondary_emotion": "次要情绪或空字符串",
                "confidence": 0.0,
                "keywords": ["情绪关键词"],
            },
            "style": {
                "theme": "healing/warm/vintage/minimal/cute/cool/elegant/calm",
                "font": "handwriting/serif/sans-serif/brush",
                "color_palette": ["#FAF6F0", "#C4A882", "#5C4A3A"],
                "layout_style": "minimal/diary/collage",
                "preferred_density": "low/medium",
                "preferred_color_tone": ["warm", "soft"],
            },
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


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
    semantic_signals = " ".join(
        [
            visual_brief.scene,
            visual_brief.sub_scene,
            *visual_brief.objects,
            *visual_brief.required_concepts,
            *visual_brief.visual_keywords,
        ]
    ).lower()
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for index, fewshot in enumerate(MATERIAL_RETRIEVAL_FEWSHOTS):
        score = 0.0
        if visual_brief.sub_scene in fewshot["sub_scenes"]:
            score += 7.0
        if visual_brief.scene in fewshot["scenes"]:
            score += 5.0
        if visual_brief.content_length in fewshot["content_lengths"]:
            score += 2.0
        score += min(4.0, sum(1.0 for token in fewshot["keywords"] if token.lower() in semantic_signals))
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


LAYOUT_SELECTION_SYSTEM_PROMPT = """你是 onePage 手帐的方案选择助手。
只能从后端提供的完整候选方案中选择一个 template_id，并给出简短自然的标题。
不能输出正文、素材、角色、坐标、尺寸、透明度、optional_slots 或 z_index。
只输出 JSON。"""


def build_layout_selection_prompt(brief: VisualBrief, plans: list[Any]) -> str:
    candidates = [
        {
            "template_id": plan.template_id,
            "layout_type": plan.template_id.split("_")[0],
            "score": plan.score,
            "roles": sorted(plan.materials),
        }
        for plan in plans
    ]
    return json.dumps(
        {
            "instruction": "从候选完整方案中选择最适合当前记录的一项",
            "visual_brief": brief.model_dump(mode="json"),
            "candidates": candidates,
            "output_schema": {"template_id": "候选 ID", "title": "不超过20个汉字的标题"},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


IMAGE_DESCRIPTION_DEFAULT_PROMPT = "请描述图片中的主体、动作、场景、物体、颜色、可见文字和整体氛围。"


def build_material_visual_metadata_prompt(prepared: list[dict[str, Any]]) -> str:
    items = []
    for item in prepared:
        material = item["material"]
        meta = dict(material.meta_info or {})
        items.append(
            {
                "label": item["label"],
                "filename": meta.get("filename") or meta.get("display_name") or "",
                "material_type": str(material.material_type or ""),
                "category": meta.get("category") or "",
            }
        )
    return (
        "分析这张手帐素材编号宫格，只输出 JSON，不要解释、Markdown 或代码块。每个编号必须且只能返回一条。\n"
        "字段：label、subjects、actions、scenes、objects、detected_text、text_heavy、risk_flags、"
        "suggested_role、background_safe、visual_style、color_tone、complexity、density。\n"
        "complexity 和 density 只能是 low、medium、high。suggested_role 只能是 background、"
        "focal_sticker、supporting_sticker、tape、frame、decoration、none。\n"
        "risk_flags 只能使用 valentine、wedding、romance、festival_text、medical、sick、wheelchair、"
        "elderly_care、religion、business_sales、party。识别可见中文、英文和日文；没有文字时 "
        "detected_text 为空字符串。文件名只能帮助理解素材，不得当作图片可见文字，text_heavy 只能根据图片实际文字占比判断。\n"
        f"素材编号：{json.dumps(items, ensure_ascii=False)}\n"
        '输出格式：{"items":[{"label":"A01","subjects":[],"actions":[],"scenes":[],"objects":[],'
        '"detected_text":"","text_heavy":false,"risk_flags":[],"suggested_role":"decoration",'
        '"background_safe":false,"visual_style":"","color_tone":"","complexity":"low","density":"low"}]}'
    )
