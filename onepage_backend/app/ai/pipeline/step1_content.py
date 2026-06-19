import structlog

from app.ai.pipeline.llm_json import run_json_llm_step

logger = structlog.get_logger(__name__)


DEFAULT_CONSTRAINTS = {
    "prefer_neutral": True,
    "prefer_gentle": True,
    "prefer_low_density": True,
    "avoid_festival": True,
    "avoid_romance": True,
    "avoid_party": True,
    "avoid_unrelated_people": False,
    "avoid_text_heavy_sticker": False,
}


async def run_content_understanding(ctx: dict) -> dict:
    """Step 1: Understand content from text, images, and audio."""
    input_json = ctx["input_json"]
    result = {
        "text_analysis": {},
        "image_descriptions": [],
        "audio_transcription": "",
        "audio_emotion": "neutral",
    }

    # Process text
    text = input_json.get("text", "") or input_json.get("content_text", "")
    if text:
        try:
            from app.ai.gateway.deepseek_client import DeepSeekClient
            from app.ai.prompts.content_understanding import SYSTEM_PROMPT, USER_TEMPLATE

            result["text_analysis"] = await run_json_llm_step(
                client_factory=DeepSeekClient,
                messages=[{"role": "user", "content": USER_TEMPLATE.format(content=text)}],
                system_prompt=SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=4096,
                response_format={"type": "json_object"},
                default={},
            )
        except Exception as e:
            logger.warning("step1_text_failed", error=str(e))
            result["text_analysis"] = {"summary": text[:200]}

    # Process images (delegated to Celery worker — here we just note their presence)
    image_urls = input_json.get("image_urls", [])
    if image_urls:
        for url in image_urls:
            result["image_descriptions"].append({"url": url, "description": ""})

    # Process audio
    audio_url = input_json.get("audio_url", "")
    if audio_url:
        result["audio_transcription"] = input_json.get("audio_text", "")

    # Pass user mood from input
    result["user_mood"] = input_json.get("mood", "")
    semantic_result = build_semantic_result(
        text=text or result.get("audio_transcription", ""),
        text_analysis=result.get("text_analysis", {}),
        mood=result.get("user_mood", ""),
    )
    result.update(semantic_result)
    if isinstance(result.get("text_analysis"), dict):
        result["text_analysis"] = {**result["text_analysis"], **semantic_result}

    print(
        "STEP1_SEMANTIC_RESULT "
        f"task_id={ctx.get('task_id')} "
        f"scene={semantic_result['scene']} "
        f"sub_scene={semantic_result['sub_scene']} "
        f"intent={semantic_result['intent']} "
        f"positive_tags={semantic_result['positive_tags']} "
        f"avoid_tags={semantic_result['avoid_tags']}",
        flush=True,
    )

    return result


def build_semantic_result(*, text: str, text_analysis: dict | None = None, mood: str = "") -> dict:
    """Build a conservative semantic layer while preserving the existing Step1 shape."""

    text_analysis = text_analysis if isinstance(text_analysis, dict) else {}
    haystack = " ".join(
        str(part or "")
        for part in (
            text,
            mood,
            text_analysis.get("summary"),
            text_analysis.get("scene"),
            text_analysis.get("topic"),
        )
    ).lower()
    constraints = dict(DEFAULT_CONSTRAINTS)

    study_tokens = (
        "资料分析",
        "行测",
        "申论",
        "刷题",
        "考试",
        "学习",
        "复习",
        "笔记",
        "错题",
        "上岸",
        "进步",
        "自信",
        "做题",
        "备考",
        "成绩",
        "计划",
        "努力",
        "复盘",
        "study",
        "exam",
    )
    food_tokens = (
        "铁锅炖",
        "吃",
        "吃了",
        "好吃",
        "饺子",
        "饺子店",
        "餐厅",
        "咖啡",
        "奶茶",
        "美食",
        "点赞",
        "好评",
        "用餐",
        "食物",
        "餐饮",
        "火锅",
        "烧烤",
        "小龙虾",
        "饭",
        "菜",
        "甜品",
        "food",
        "coffee",
    )
    health_tokens = (
        "身体不舒服",
        "不舒服",
        "小柴胡",
        "喝药",
        "吃药",
        "药",
        "感冒",
        "发烧",
        "咳嗽",
        "头疼",
        "好一点",
        "恢复",
        "休息",
        "healing",
        "sick",
        "medicine",
        "recover",
    )
    emotion_tokens = (
        "难过",
        "压力",
        "崩溃",
        "累",
        "焦虑",
        "不开心",
        "烦",
        "委屈",
        "emo",
        "sad",
        "anxious",
    )

    if _contains_any(haystack, study_tokens):
        constraints.update(
            {
                "avoid_unrelated_people": True,
                "avoid_text_heavy_sticker": True,
            }
        )
        return {
            "topic": _pick_topic(text, "学习复盘"),
            "scene": "self_growth",
            "sub_scene": "study_reflection",
            "intent": "self_encouragement",
            "keywords": _collect_keywords(text, study_tokens),
            "emotion_hint": mood or "calm",
            "style_hint": "minimal_healing",
            "positive_tags": ["study", "exam_prep", "self_growth", "achievement", "encouragement", "daily"],
            "avoid_tags": ["festival", "romance", "valentine", "wedding", "party", "unrelated_people"],
            "semantic_constraints": constraints,
        }

    if _contains_any(haystack, food_tokens):
        constraints.update({"avoid_unrelated_people": True, "avoid_party": True, "avoid_text_heavy_sticker": True})
        return {
            "topic": _pick_topic(text, "美食小记"),
            "scene": "daily_life",
            "sub_scene": "food_review",
            "intent": "food_record",
            "keywords": _collect_keywords(text, food_tokens),
            "emotion_hint": mood or "happy",
            "style_hint": "warm_daily",
            "positive_tags": ["food", "daily", "warm", "happy", "review"],
            "avoid_tags": [
                "romance",
                "valentine",
                "wedding",
                "party",
                "festival",
                "congratulations",
                "bouquet",
                "gift",
                "unrelated_people",
                "religion",
                "crest",
                "dance",
                "ballet",
            ],
            "semantic_constraints": constraints,
        }

    if _contains_any(haystack, health_tokens):
        constraints.update({"avoid_unrelated_people": True, "avoid_text_heavy_sticker": True})
        return {
            "topic": _pick_topic(text, "身体恢复小记"),
            "scene": "daily_life",
            "sub_scene": "health_recovery",
            "intent": "recovery_record",
            "keywords": _collect_keywords(text, health_tokens),
            "emotion_hint": mood or "healing",
            "style_hint": "gentle_minimal",
            "positive_tags": ["daily", "healing", "warm", "rest", "recovery"],
            "avoid_tags": [
                "romance",
                "valentine",
                "wedding",
                "party",
                "festival",
                "congratulations",
                "bouquet",
                "gift",
                "business_sales",
                "expensive",
                "unrelated_people",
                "religion",
                "crest",
                "dance",
                "ballet",
            ],
            "semantic_constraints": constraints,
        }

    if _contains_any(haystack, emotion_tokens):
        constraints.update({"avoid_unrelated_people": True, "avoid_text_heavy_sticker": True})
        return {
            "topic": _pick_topic(text, "情绪记录"),
            "scene": "emotion_record",
            "sub_scene": "mood_release",
            "intent": "emotional_expression",
            "keywords": _collect_keywords(text, emotion_tokens),
            "emotion_hint": mood or "healing",
            "style_hint": "gentle_minimal",
            "positive_tags": ["calm", "healing", "gentle", "minimal"],
            "avoid_tags": ["party", "festival", "high_saturation", "too_loud"],
            "semantic_constraints": constraints,
        }

    existing_scene = str(text_analysis.get("scene") or "").strip()
    if existing_scene and existing_scene not in {"unknown", "none", "null"}:
        scene = existing_scene
    else:
        scene = "daily_life"

    return {
        "topic": _pick_topic(text, str(text_analysis.get("topic") or "日常记录")),
        "scene": scene,
        "sub_scene": str(text_analysis.get("sub_scene") or "general_daily"),
        "intent": str(text_analysis.get("intent") or "daily_record"),
        "keywords": _collect_keywords(text, ()),
        "emotion_hint": mood or "neutral",
        "style_hint": "warm_daily",
        "positive_tags": ["daily", "neutral", "warm"],
        "avoid_tags": ["wedding", "valentine", "strong_festival"],
        "semantic_constraints": constraints,
    }


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token.lower() in text for token in tokens)


def _collect_keywords(text: str, tokens: tuple[str, ...]) -> list[str]:
    found = [token for token in tokens if token and token.lower() in str(text or "").lower()]
    if found:
        return found[:8]
    words = [item.strip("，。,.!！？?、 ") for item in str(text or "").split() if item.strip()]
    return words[:8]


def _pick_topic(text: str, fallback: str) -> str:
    clean = str(text or "").strip()
    if not clean:
        return fallback
    return clean[:24]
