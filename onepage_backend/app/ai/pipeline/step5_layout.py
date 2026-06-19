import json
import structlog

from app.ai.fallback.templates import get_fallback_layout
from app.ai.pipeline.llm_json import extract_message_content
from app.ai.prompts.layout_generation import SYSTEM_PROMPT, USER_TEMPLATE

logger = structlog.get_logger(__name__)


async def run_layout_generation(ctx: dict) -> str:
    """Step 5: Generate Layout JSON via LLM."""
    step1 = ctx.get("step1", {})
    step2 = ctx.get("step2", {})
    step3 = ctx.get("step3", {})
    step4 = _layout_material_context(ctx.get("step4_review") or ctx.get("step4", {}))
    input_json = ctx["input_json"]
    print(f"STEP5_MODEL_START task_id={ctx.get('task_id')}", flush=True)
    counts = _reviewed_group_counts(step4)
    print(
        "STEP5_REVIEWED_CANDIDATES "
        f"task_id={ctx.get('task_id')} "
        f"background={counts.get('background', 0)} "
        f"decoration={counts.get('decoration', 0)} "
        f"sticker={counts.get('sticker', 0)} "
        f"fallback_mode={step4.get('fallback_mode') if isinstance(step4, dict) else None}",
        flush=True,
    )

    # Build context for the prompt
    content_text = input_json.get("text", "") or input_json.get("content_text", "")
    image_info = json.dumps(step1.get("image_descriptions", []), ensure_ascii=False)
    journal_context = ctx.get("journal_context", {}) if isinstance(ctx.get("journal_context"), dict) else {}
    authoritative_context = build_authoritative_context(journal_context)
    weather = authoritative_context["weather_text"] or ""
    mood = input_json.get("mood", step2.get("primary_emotion", ""))
    page_date = authoritative_context["date_text"]
    print(
        "STEP5_AUTHORITATIVE_CONTEXT "
        f"task_id={ctx.get('task_id')} "
        f"date={page_date} "
        f"weather={weather or 'unknown'} "
        f"weather_icon={authoritative_context['weather_icon'] or ''}",
        flush=True,
    )

    # Try primary model (Qwen)
    try:
        result = await _call_qwen(content_text, image_info, step3, step2, step4, weather, mood, page_date, authoritative_context)
        if result:
            print(f"STEP5_MODEL_OK task_id={ctx.get('task_id')} model=qwen", flush=True)
            return result
    except Exception as e:
        logger.warning("step5_qwen_failed", error=str(e))

    # Try fallback model (DeepSeek)
    try:
        result = await _call_deepseek(content_text, image_info, step3, step2, step4, weather, mood, page_date, authoritative_context)
        if result:
            print(f"STEP5_MODEL_OK task_id={ctx.get('task_id')} model=deepseek", flush=True)
            return result
    except Exception as e:
        logger.warning("step5_deepseek_failed", error=str(e))

    # Ultimate fallback
    emotion = step2.get("primary_emotion", "neutral")
    print(f"STEP5_MODEL_FALLBACK task_id={ctx.get('task_id')} emotion={emotion}", flush=True)
    return json.dumps(get_fallback_layout(emotion, content_text=content_text, page_date=page_date), ensure_ascii=False)


def _reviewed_group_counts(materials: dict) -> dict[str, int]:
    if not isinstance(materials, dict):
        return {}
    groups = materials.get("groups", []) if isinstance(materials.get("groups"), list) else []
    counts: dict[str, int] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        counts[str(group.get("material_type") or "unknown")] = len(
            group.get("items", []) if isinstance(group.get("items"), list) else []
        )
    return counts


def _layout_material_context(materials: dict) -> dict:
    if not isinstance(materials, dict):
        return {}
    return {
        "summary": materials.get("summary", {}),
        "groups": materials.get("groups", []),
        "reviewed_candidates": materials.get("reviewed_candidates", {}),
        "fallback_mode": materials.get("fallback_mode", "none"),
        "review_summary": materials.get("review_summary", {}),
    }


def build_authoritative_context(journal_context: dict) -> dict:
    header = journal_context.get("journal_header", {}) if isinstance(journal_context.get("journal_header"), dict) else {}
    datetime_context = journal_context.get("datetime", {}) if isinstance(journal_context.get("datetime"), dict) else {}
    if not datetime_context.get("date"):
        from app.ai.mcp_client import build_system_datetime_context

        datetime_context = build_system_datetime_context("Asia/Shanghai")
    weather_success = bool(journal_context.get("weather_success"))
    weather_context = journal_context.get("weather", {}) if isinstance(journal_context.get("weather"), dict) else {}
    location_context = journal_context.get("location", {}) if isinstance(journal_context.get("location"), dict) else {}
    return {
        "date_text": str(header.get("date_text") or datetime_context.get("date") or "").strip(),
        "time": str(datetime_context.get("time") or journal_context.get("time") or "").strip(),
        "weekday": str(datetime_context.get("weekday") or journal_context.get("weekday") or "").strip(),
        "timezone": str(datetime_context.get("timezone") or journal_context.get("timezone") or "").strip(),
        "weather_text": str(header.get("weather_text") or "").strip() if weather_success else "",
        "weather_icon": str(header.get("weather_icon") or "").strip() if weather_success else "",
        "weather_icon_key": str(weather_context.get("icon_key") or "").strip() if weather_success else "",
        "weather_status": str(journal_context.get("weather_status") or ("success" if weather_success else "unavailable")),
        "temperature": str(weather_context.get("temperature_celsius") or journal_context.get("temperature") or "").strip() if weather_success else "",
        "weather_success": weather_success,
        "location": location_context,
        "location_text": str(location_context.get("district") or location_context.get("city") or location_context.get("input_location") or "").strip(),
        "location_status": str(journal_context.get("location_status") or ""),
        "location_source": str(location_context.get("location_source") or ""),
        "source": journal_context.get("source"),
        "tool_success": bool(journal_context.get("tool_success")),
    }


async def _call_qwen(
    content_text,
    image_info,
    style,
    emotion_data,
    materials,
    weather,
    mood,
    page_date,
    authoritative_context,
) -> str | None:
    from app.ai.gateway.qwen_client import QwenClient

    prompt = USER_TEMPLATE.format(
        content_text=content_text or "记录今日点滴",
        image_info=image_info,
        theme=style.get("theme", "healing"),
        font=style.get("font", "handwriting"),
        color_palette=json.dumps(style.get("color_palette", [])),
        layout_style=style.get("layout_style", "minimal"),
        emotion=json.dumps(emotion_data, ensure_ascii=False),
        recommended_materials=json.dumps(materials, ensure_ascii=False),
        authoritative_journal_context=json.dumps(authoritative_context, ensure_ascii=False),
        weather=weather,
        mood=mood or "记录",
        page_date=page_date or "",
    )
    return await _call_layout_model(
        client_factory=QwenClient,
        prompt=prompt,
    )


async def _call_deepseek(
    content_text,
    image_info,
    style,
    emotion_data,
    materials,
    weather,
    mood,
    page_date,
    authoritative_context,
) -> str | None:
    from app.ai.gateway.deepseek_client import DeepSeekClient

    prompt = USER_TEMPLATE.format(
        content_text=content_text or "记录今日点滴",
        image_info=image_info,
        theme=style.get("theme", "healing"),
        font=style.get("font", "handwriting"),
        color_palette=json.dumps(style.get("color_palette", [])),
        layout_style=style.get("layout_style", "minimal"),
        emotion=json.dumps(emotion_data, ensure_ascii=False),
        recommended_materials=json.dumps(materials, ensure_ascii=False),
        authoritative_journal_context=json.dumps(authoritative_context, ensure_ascii=False),
        weather=weather,
        mood=mood or "记录",
        page_date=page_date or "",
    )
    return await _call_layout_model(
        client_factory=DeepSeekClient,
        prompt=prompt,
    )


async def _call_layout_model(*, client_factory, prompt: str) -> str | None:
    client = client_factory()
    try:
        response = await client.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        content = extract_message_content(response)
        return content or None
    finally:
        await client.close()
