from __future__ import annotations

from typing import Any

import structlog

from app.ai.gateway.deepseek_client import DeepSeekClient
from app.ai.pipeline.llm_json import run_json_llm_step
from app.ai.prompt_registry import UNIFIED_ANALYSIS_SYSTEM_PROMPT, build_unified_analysis_prompt


logger = structlog.get_logger(__name__)

DEFAULT_EXCLUDED_CONCEPTS = [
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

DEFAULT_STYLE = {
    "theme": "healing",
    "font": "handwriting",
    "color_palette": ["#FAF6F0", "#C4A882", "#5C4A3A"],
    "layout_style": "minimal",
    "preferred_density": "low",
    "preferred_color_tone": ["warm", "soft"],
}


async def run_content_understanding(ctx: dict) -> dict:
    input_json = ctx.get("input_json") if isinstance(ctx.get("input_json"), dict) else {}
    text = str(input_json.get("text") or input_json.get("content_text") or "").strip()
    mood = str(input_json.get("mood") or "").strip()
    prompt = build_unified_analysis_prompt(
        user_text=text,
        mood=mood,
        environment_context=input_json.get("environment_context"),
        user_preferences=ctx.get("user_preferences"),
    )
    try:
        raw = await run_json_llm_step(
            client_factory=DeepSeekClient,
            messages=[{"role": "user", "content": prompt}],
            system_prompt=UNIFIED_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=1800,
            response_format={"type": "json_object"},
            default={},
        )
    except Exception as exc:
        logger.warning("unified_analysis_failed", error=str(exc))
        raw = {}

    analysis = normalize_unified_analysis(raw, user_text=text, user_mood=mood)
    semantic = analysis["semantic"]
    result = {
        "text_analysis": semantic,
        "image_descriptions": [
            {"url": str(url), "description": ""}
            for url in input_json.get("image_urls", [])
            if str(url).strip()
        ],
        "audio_transcription": str(input_json.get("audio_text") or ""),
        "audio_emotion": "neutral",
        "user_mood": mood,
        **semantic,
        "sentiment": analysis["sentiment"],
        "style": analysis["style"],
    }
    print(
        "STEP1_UNIFIED_ANALYSIS "
        f"task_id={ctx.get('task_id')} scene={semantic['scene']} sub_scene={semantic['sub_scene']} "
        f"intent={semantic['intent']} keywords={semantic['keywords']} "
        f"emotion={analysis['sentiment']['primary_emotion']} theme={analysis['style']['theme']}",
        flush=True,
    )
    return result


def normalize_unified_analysis(raw: Any, *, user_text: str, user_mood: str) -> dict[str, Any]:
    payload = raw if isinstance(raw, dict) else {}
    semantic_raw = payload.get("semantic") if isinstance(payload.get("semantic"), dict) else {}
    sentiment_raw = payload.get("sentiment") if isinstance(payload.get("sentiment"), dict) else {}
    style_raw = payload.get("style") if isinstance(payload.get("style"), dict) else {}

    topic = _text(semantic_raw.get("topic"), "日常记录", 40)
    title_hint = _text(semantic_raw.get("title_hint"), topic, 40)
    semantic = {
        "summary": _text(semantic_raw.get("summary"), user_text[:200], 240),
        "topic": topic,
        "scene": _identifier(semantic_raw.get("scene"), "daily_life"),
        "sub_scene": _identifier(semantic_raw.get("sub_scene"), "general_daily"),
        "intent": _identifier(semantic_raw.get("intent"), "daily_record"),
        "primary_subject": _text(semantic_raw.get("primary_subject"), "", 80),
        "primary_action": _text(semantic_raw.get("primary_action"), "", 80),
        "environment": _list(semantic_raw.get("environment"), 8),
        "objects": _list(semantic_raw.get("objects"), 12),
        "keywords": _list(semantic_raw.get("keywords"), 12),
        "visual_keywords": _list(semantic_raw.get("visual_keywords"), 12),
        "required_concepts": _list(semantic_raw.get("required_concepts"), 10),
        "positive_tags": _list(semantic_raw.get("positive_tags"), 10),
        "avoid_tags": _dedupe([*DEFAULT_EXCLUDED_CONCEPTS, *_list(semantic_raw.get("avoid_tags"), 16)]),
        "excluded_concepts": _dedupe(
            [*DEFAULT_EXCLUDED_CONCEPTS, *_list(semantic_raw.get("avoid_tags"), 16)]
        ),
        "title_hint": title_hint,
        "emotion_hint": _text(sentiment_raw.get("primary_emotion"), user_mood or "neutral", 32),
    }
    sentiment = {
        "primary_emotion": _text(sentiment_raw.get("primary_emotion"), _fallback_emotion(user_mood), 32),
        "secondary_emotion": _text(sentiment_raw.get("secondary_emotion"), "", 32),
        "confidence": _confidence(sentiment_raw.get("confidence")),
        "keywords": _list(sentiment_raw.get("keywords"), 8),
    }
    style = {
        "theme": _choice(style_raw.get("theme"), {"healing", "warm", "vintage", "minimal", "cute", "cool", "elegant", "calm"}, DEFAULT_STYLE["theme"]),
        "font": _choice(style_raw.get("font"), {"handwriting", "serif", "sans-serif", "brush"}, DEFAULT_STYLE["font"]),
        "color_palette": _colors(style_raw.get("color_palette")) or list(DEFAULT_STYLE["color_palette"]),
        "layout_style": _choice(style_raw.get("layout_style"), {"minimal", "diary", "collage"}, DEFAULT_STYLE["layout_style"]),
        "preferred_density": _choice(style_raw.get("preferred_density"), {"low", "medium"}, DEFAULT_STYLE["preferred_density"]),
        "preferred_color_tone": _list(style_raw.get("preferred_color_tone"), 6)
        or list(DEFAULT_STYLE["preferred_color_tone"]),
    }
    return {"semantic": semantic, "sentiment": sentiment, "style": style}


def _fallback_emotion(mood: str) -> str:
    return {
        "开心": "happy",
        "平静": "calm",
        "放松": "calm",
        "兴奋": "excited",
        "难过": "sad",
        "低落": "sad",
        "焦虑": "anxious",
    }.get(str(mood or "").strip(), "neutral")


def _identifier(value: Any, default: str) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    return text[:64] if text else default


def _text(value: Any, default: str, limit: int) -> str:
    text = str(value or "").strip()
    return (text or default)[:limit]


def _list(value: Any, limit: int) -> list[str]:
    values = value if isinstance(value, list) else []
    return _dedupe([str(item).strip()[:60] for item in values if str(item).strip()])[:limit]


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


def _choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else default


def _colors(value: Any) -> list[str]:
    return [item for item in _list(value, 5) if len(item) == 7 and item.startswith("#")]


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.3
