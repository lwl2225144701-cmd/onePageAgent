from __future__ import annotations

from typing import Any

from app.ai.layout_v2.schemas import VisualBrief


BASE_EXCLUSIONS = [
    "valentine",
    "wedding",
    "romance",
    "festival_text",
    "medical",
    "sick",
    "wheelchair",
    "elderly_care",
    "religion",
    "business_sales",
    "party",
]

SCENE_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "tokens": ("猫", "猫猫", "猫咪", "小猫", "抱猫", "pet", "cat"),
        "scene": "home",
        "sub_scene": "pet_companion",
        "subject": "猫咪或陪伴猫咪的人物",
        "action": "陪伴、抱猫或与猫咪互动",
        "environment": ["home", "living_room", "bedroom"],
        "objects": ["cat"],
        "concepts": ["cat", "pet", "companion"],
        "title": "被猫治愈的一天",
    },
    {
        "tokens": ("出门", "去玩", "游玩", "散步", "郊游", "逛公园", "outing", "travel"),
        "scene": "outing",
        "sub_scene": "weekend_leisure",
        "subject": "出门游玩的人物",
        "action": "散步、旅行或探索",
        "environment": ["park", "street", "outdoor"],
        "objects": [],
        "concepts": ["outing", "travel", "leisure"],
        "title": "今天去哪里玩",
    },
    {
        "tokens": ("铁锅炖", "饺子", "好吃", "美食", "餐厅", "咖啡", "奶茶", "火锅", "烧烤", "小龙虾", "甜品", "做饭", "咖喱"),
        "scene": "food",
        "sub_scene": "food_record",
        "subject": "食物或用餐场景",
        "action": "用餐、烹饪或品尝",
        "environment": ["restaurant", "cafe", "kitchen"],
        "objects": ["food"],
        "concepts": ["food", "meal", "cooking"],
        "title": "今天的美味时刻",
    },
    {
        "tokens": ("学习", "复习", "考试", "图书馆", "笔记", "study", "exam"),
        "scene": "study",
        "sub_scene": "study_reflection",
        "subject": "学习中的人物或书本文具",
        "action": "学习、阅读或整理笔记",
        "environment": ["library", "school", "desk"],
        "objects": ["book", "notes"],
        "concepts": ["study", "reading", "notes"],
        "title": "认真学习的一天",
    },
    {
        "tokens": ("工作", "加班", "项目", "汇报", "ppt", "deadline", "office"),
        "scene": "work",
        "sub_scene": "office_record",
        "subject": "工作中的人物或办公物件",
        "action": "工作、整理或汇报",
        "environment": ["office", "desk", "urban"],
        "objects": ["computer", "document"],
        "concepts": ["work", "office", "computer"],
        "title": "今天的工作片段",
    },
    {
        "tokens": ("海边", "旅行", "出发", "机场", "行李", "露营", "trip", "beach"),
        "scene": "travel",
        "sub_scene": "travel_memory",
        "subject": "旅行中的人物或交通物件",
        "action": "旅行、出发或探索",
        "environment": ["travel", "beach", "outdoor"],
        "objects": ["luggage", "vehicle"],
        "concepts": ["travel", "outing", "explore"],
        "title": "旅途中的一页",
    },
    {
        "tokens": ("看书", "阅读", "书店", "read", "book"),
        "scene": "reading",
        "sub_scene": "quiet_reading",
        "subject": "阅读中的人物或书本",
        "action": "阅读",
        "environment": ["cafe", "library", "home"],
        "objects": ["book"],
        "concepts": ["reading", "book"],
        "title": "安静读书的下午",
    },
    {
        "tokens": ("跑步", "健身", "运动", "瑜伽", "游泳", "exercise", "running"),
        "scene": "exercise",
        "sub_scene": "exercise_record",
        "subject": "运动中的人物",
        "action": "跑步、健身或运动",
        "environment": ["outdoor", "gym", "park"],
        "objects": [],
        "concepts": ["exercise", "running", "sport"],
        "title": "今天也坚持运动",
    },
)


def build_visual_brief(*, text: str, mood: str = "", semantic: dict[str, Any] | None = None) -> VisualBrief:
    source_text = str(text or "").strip()
    lowered = source_text.lower()
    semantic = semantic if isinstance(semantic, dict) else {}
    profile = next((item for item in SCENE_PROFILES if any(token.lower() in lowered for token in item["tokens"])), None)
    length = _content_length(source_text)
    emotion = str(mood or semantic.get("emotion_hint") or "neutral").strip() or "neutral"
    if profile is None:
        profile = {
            "scene": str(semantic.get("scene") or "daily_life"),
            "sub_scene": str(semantic.get("sub_scene") or "general_daily"),
            "subject": "",
            "action": "",
            "environment": [],
            "objects": [],
            "concepts": _semantic_keywords(semantic),
            "title": str(semantic.get("topic") or "今天的一页"),
        }

    exclusions = list(BASE_EXCLUSIONS)
    if profile["scene"] == "food":
        exclusions.extend(["bouquet", "gift", "dance", "ballet", "family_crest"])
    if profile["scene"] == "outing":
        exclusions.extend(["bouquet", "celebration", "elderly_care"])
    if profile["scene"] == "home" and profile["sub_scene"] == "pet_companion":
        exclusions.extend(["business", "celebration"])

    title = str(semantic.get("topic") or profile["title"]).strip()
    if not title or title == source_text:
        title = str(profile["title"])
    visual_keywords = _dedupe([*profile["concepts"], *_semantic_keywords(semantic)])
    return VisualBrief(
        topic=title,
        content_type={"short": "short_note", "medium": "medium_journal", "long": "long_journal"}[length],
        scene=profile["scene"],
        sub_scene=profile["sub_scene"],
        primary_subject=profile["subject"],
        primary_action=profile["action"],
        environment=profile["environment"],
        objects=profile["objects"],
        emotion=emotion,
        visual_keywords=visual_keywords,
        required_concepts=profile["concepts"],
        excluded_concepts=_dedupe(exclusions),
        title_hint=title[:40] or "今天的一页",
        content_length=length,
        preferred_density="low" if length in {"short", "long"} else "medium",
        preferred_color_tone=_color_tones(emotion),
    )


def build_visual_brief_from_context(ctx: dict[str, Any]) -> VisualBrief:
    input_json = ctx.get("input_json") if isinstance(ctx.get("input_json"), dict) else {}
    step1 = ctx.get("step1") if isinstance(ctx.get("step1"), dict) else {}
    text = str(input_json.get("text") or input_json.get("content_text") or "")
    mood = str(input_json.get("mood") or step1.get("user_mood") or "")
    try:
        return build_visual_brief(text=text, mood=mood, semantic=step1)
    except Exception:
        return VisualBrief(
            topic="今天的一页",
            content_type="short_note" if len(text) <= 32 else "medium_journal",
            scene="daily_life",
            sub_scene="general_daily",
            emotion=mood or "neutral",
            title_hint="今天的一页",
            content_length="short" if len(text) <= 32 else "medium",
            excluded_concepts=BASE_EXCLUSIONS,
        )


def _content_length(text: str) -> str:
    length = len(text.strip())
    if length <= 32:
        return "short"
    if length <= 150:
        return "medium"
    return "long"


def _semantic_keywords(semantic: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("keywords", "positive_tags"):
        raw = semantic.get(key)
        if isinstance(raw, list):
            values.extend(str(item) for item in raw)
    return _dedupe(values)[:8]


def _color_tones(emotion: str) -> list[str]:
    lowered = emotion.lower()
    if any(token in lowered for token in ("难过", "焦虑", "sad", "anxious", "平静", "calm")):
        return ["muted", "soft"]
    if any(token in lowered for token in ("兴奋", "开心", "happy", "excited")):
        return ["warm", "fresh"]
    return ["warm", "soft"]


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result
