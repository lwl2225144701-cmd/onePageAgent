import json
import structlog

logger = structlog.get_logger(__name__)


async def run_sentiment_analysis(ctx: dict) -> dict:
    """Step 2: Analyze sentiment and emotion from content."""
    content = ctx.get("step1", {})

    try:
        from app.ai.gateway.deepseek_client import DeepSeekClient
        from app.ai.prompts.sentiment_analysis import SYSTEM_PROMPT, USER_TEMPLATE

        client = DeepSeekClient()
        resp = await client.chat(
            messages=[{
                "role": "user",
                "content": USER_TEMPLATE.format(
                    content_text=json.dumps(content.get("text_analysis", {}), ensure_ascii=False),
                    image_descriptions=json.dumps(content.get("image_descriptions", []), ensure_ascii=False),
                    user_mood=content.get("user_mood", ""),
                ),
            }],
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        result_str = resp.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        result = json.loads(result_str) if isinstance(result_str, str) else result_str
        await client.close()
        return result
    except Exception as e:
        logger.warning("step2_sentiment_failed", error=str(e))
        # Fallback to user mood or neutral
        user_mood = content.get("user_mood", "")
        mood_map = {
            "开心": "happy", "高兴": "happy", "快乐": "happy",
            "难过": "sad", "伤心": "sad",
            "兴奋": "excited", "激动": "excited",
            "平静": "calm", "安静": "calm",
            "怀旧": "nostalgic",
        }
        return {
            "primary_emotion": mood_map.get(user_mood, "neutral"),
            "secondary_emotion": "",
            "confidence": 0.3,
            "keywords": [user_mood] if user_mood else [],
        }
