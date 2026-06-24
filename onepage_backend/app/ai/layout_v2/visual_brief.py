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


def build_visual_brief(*, text: str, mood: str = "", semantic: dict[str, Any] | None = None) -> VisualBrief:
    source_text = str(text or "").strip()
    semantic = semantic if isinstance(semantic, dict) else {}
    length = _content_length(source_text)
    scene = _identifier(semantic.get("scene"), "daily_life")
    sub_scene = _identifier(semantic.get("sub_scene"), "general_daily")
    topic = str(semantic.get("topic") or semantic.get("title_hint") or "今天的一页").strip()[:40] or "今天的一页"
    required_concepts = _semantic_list(semantic, "required_concepts")
    visual_keywords = _dedupe(
        [
            *_semantic_list(semantic, "visual_keywords"),
            *_semantic_list(semantic, "keywords"),
            *_semantic_list(semantic, "positive_tags"),
        ]
    )[:12]
    excluded = _dedupe(
        [
            *BASE_EXCLUSIONS,
            *_semantic_list(semantic, "excluded_concepts"),
            *_semantic_list(semantic, "avoid_tags"),
        ]
    )
    preferred_density = str(semantic.get("preferred_density") or "").strip().lower()
    if preferred_density not in {"low", "medium"}:
        preferred_density = "low" if length in {"short", "long"} else "medium"
    preferred_color_tone = _semantic_list(semantic, "preferred_color_tone") or ["warm", "soft"]
    return VisualBrief(
        topic=topic,
        content_type={"short": "short_note", "medium": "medium_journal", "long": "long_journal"}[length],
        scene=scene,
        sub_scene=sub_scene,
        primary_subject=str(semantic.get("primary_subject") or "").strip()[:80],
        primary_action=str(semantic.get("primary_action") or "").strip()[:80],
        environment=_semantic_list(semantic, "environment"),
        objects=_semantic_list(semantic, "objects"),
        emotion=str(mood or semantic.get("emotion_hint") or "neutral").strip() or "neutral",
        visual_keywords=visual_keywords,
        required_concepts=required_concepts,
        excluded_concepts=excluded,
        title_hint=str(semantic.get("title_hint") or topic).strip()[:40] or topic,
        content_length=length,
        preferred_density=preferred_density,
        preferred_color_tone=preferred_color_tone,
    )


def build_visual_brief_from_context(ctx: dict[str, Any]) -> VisualBrief:
    input_json = ctx.get("input_json") if isinstance(ctx.get("input_json"), dict) else {}
    step1 = ctx.get("step1") if isinstance(ctx.get("step1"), dict) else {}
    step3 = ctx.get("step3") if isinstance(ctx.get("step3"), dict) else {}
    semantic = {
        **step1,
        "preferred_density": step3.get("preferred_density"),
        "preferred_color_tone": step3.get("preferred_color_tone"),
    }
    text = str(input_json.get("text") or input_json.get("content_text") or "")
    mood = str(input_json.get("mood") or step1.get("user_mood") or "")
    return build_visual_brief(text=text, mood=mood, semantic=semantic)


def _content_length(text: str) -> str:
    length = len(text.strip())
    if length <= 32:
        return "short"
    if length <= 150:
        return "medium"
    return "long"


def _semantic_list(semantic: dict[str, Any], key: str) -> list[str]:
    value = semantic.get(key)
    values = value if isinstance(value, list) else []
    return _dedupe([str(item).strip() for item in values if str(item).strip()])


def _identifier(value: Any, default: str) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    return text[:64] if text else default


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
