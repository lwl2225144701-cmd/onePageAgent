import structlog

from app.ai.pipeline.llm_json import run_json_llm_step

logger = structlog.get_logger(__name__)


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

    return result
