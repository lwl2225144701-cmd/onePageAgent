import json
import structlog

from app.ai.prompts.style_inference import SYSTEM_PROMPT, USER_TEMPLATE

logger = structlog.get_logger(__name__)

DEFAULT_STYLE = {
    "theme": "healing",
    "font": "handwriting",
    "color_palette": ["#FAF6F0", "#E8B4B8", "#C4A882", "#5C4A3A"],
    "layout_style": "minimal",
}


async def run_style_inference(ctx: dict) -> dict:
    """Step 3: Infer visual style based on weighted inputs."""
    step1 = ctx.get("step1", {})
    step2 = ctx.get("step2", {})

    # Try LLM inference
    try:
        from app.ai.gateway.deepseek_client import DeepSeekClient
        client = DeepSeekClient()
        resp = await client.chat(
            messages=[{
                "role": "user",
                "content": USER_TEMPLATE.format(
                    content_analysis=json.dumps(step1.get("text_analysis", {}), ensure_ascii=False),
                    sentiment=json.dumps(step2, ensure_ascii=False),
                    weather=json.dumps(ctx["input_json"].get("weather", {}), ensure_ascii=False),
                    user_preferences=json.dumps(ctx.get("user_preferences", {}), ensure_ascii=False),
                ),
            }],
            system_prompt=SYSTEM_PROMPT,
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        result_str = resp.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        result = json.loads(result_str) if isinstance(result_str, str) else result_str
        await client.close()
        return result
    except Exception as e:
        logger.warning("step3_style_failed", error=str(e))
        return DEFAULT_STYLE
