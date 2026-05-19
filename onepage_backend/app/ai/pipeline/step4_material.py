import structlog

logger = structlog.get_logger(__name__)


async def run_material_matching(ctx: dict) -> dict:
    """Step 4: Match materials based on style, emotion, scene, and weather."""
    step2 = ctx.get("step2", {})
    step3 = ctx.get("step3", {})
    input_json = ctx["input_json"]

    emotion = step2.get("primary_emotion", "")
    style = step3.get("theme", "")
    scene = step1_scene(ctx.get("step1", {}))
    weather = input_json.get("weather", {}).get("weather", "") if isinstance(input_json.get("weather"), dict) else ""

    try:
        from app.services.material_service import MaterialService
        from app.core.database import async_session_factory

        async with async_session_factory() as db:
            svc = MaterialService(db)
            groups = await svc.recommend(style=style, emotion=emotion, scene=scene, weather=weather)
            return {"groups": groups}
    except Exception as e:
        logger.warning("step4_material_failed", error=str(e))
        return {"groups": []}


def step1_scene(step1: dict) -> str:
    text_analysis = step1.get("text_analysis", {})
    if isinstance(text_analysis, dict):
        return text_analysis.get("scene", "") or ""
    return ""
