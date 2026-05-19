import json
import structlog

from app.ai.fallback.templates import get_fallback_layout
from app.ai.prompts.layout_generation import SYSTEM_PROMPT, USER_TEMPLATE

logger = structlog.get_logger(__name__)


async def run_layout_generation(ctx: dict) -> str:
    """Step 5: Generate Layout JSON via LLM."""
    step1 = ctx.get("step1", {})
    step2 = ctx.get("step2", {})
    step3 = ctx.get("step3", {})
    step4 = ctx.get("step4", {})
    input_json = ctx["input_json"]

    # Build context for the prompt
    content_text = input_json.get("text", "") or input_json.get("content_text", "")
    image_info = json.dumps(step1.get("image_descriptions", []), ensure_ascii=False)
    weather = input_json.get("weather", {}).get("weather", "晴") if isinstance(input_json.get("weather"), dict) else "晴"
    mood = input_json.get("mood", step2.get("primary_emotion", ""))
    page_date = input_json.get("page_date", "")

    # Try primary model (Qwen)
    try:
        result = await _call_qwen(content_text, image_info, step3, step2, step4, weather, mood, page_date)
        if result:
            return result
    except Exception as e:
        logger.warning("step5_qwen_failed", error=str(e))

    # Try fallback model (DeepSeek)
    try:
        result = await _call_deepseek(content_text, image_info, step3, step2, step4, weather, mood, page_date)
        if result:
            return result
    except Exception as e:
        logger.warning("step5_deepseek_failed", error=str(e))

    # Ultimate fallback
    emotion = step2.get("primary_emotion", "neutral")
    return json.dumps(get_fallback_layout(emotion), ensure_ascii=False)


async def _call_qwen(content_text, image_info, style, emotion_data, materials, weather, mood, page_date) -> str | None:
    from app.ai.gateway.qwen_client import QwenClient

    client = QwenClient()
    prompt = USER_TEMPLATE.format(
        content_text=content_text or "记录今日点滴",
        image_info=image_info,
        theme=style.get("theme", "healing"),
        font=style.get("font", "handwriting"),
        color_palette=json.dumps(style.get("color_palette", [])),
        layout_style=style.get("layout_style", "minimal"),
        emotion=json.dumps(emotion_data, ensure_ascii=False),
        recommended_materials=json.dumps(materials, ensure_ascii=False),
        weather=weather,
        mood=mood or "记录",
        page_date=page_date or "",
    )
    resp = await client.chat(
        messages=[{"role": "user", "content": prompt}],
        system_prompt=SYSTEM_PROMPT,
        temperature=0.7,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    await client.close()

    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        content = resp.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content", "")
    if content:
        return content.strip()
    return None


async def _call_deepseek(content_text, image_info, style, emotion_data, materials, weather, mood, page_date) -> str | None:
    from app.ai.gateway.deepseek_client import DeepSeekClient

    client = DeepSeekClient()
    prompt = USER_TEMPLATE.format(
        content_text=content_text or "记录今日点滴",
        image_info=image_info,
        theme=style.get("theme", "healing"),
        font=style.get("font", "handwriting"),
        color_palette=json.dumps(style.get("color_palette", [])),
        layout_style=style.get("layout_style", "minimal"),
        emotion=json.dumps(emotion_data, ensure_ascii=False),
        recommended_materials=json.dumps(materials, ensure_ascii=False),
        weather=weather,
        mood=mood or "记录",
        page_date=page_date or "",
    )
    resp = await client.chat(
        messages=[{"role": "user", "content": prompt}],
        system_prompt=SYSTEM_PROMPT,
        temperature=0.7,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    await client.close()

    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    if content:
        return content.strip()
    return None
