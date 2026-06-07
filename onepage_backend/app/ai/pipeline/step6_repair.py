import json
import structlog

from app.ai.fallback.repairer import LayoutRepairer
from app.ai.fallback.templates import get_fallback_layout
from app.ai.fallback.validator import LayoutValidator

logger = structlog.get_logger(__name__)


async def run_validate_and_repair(ctx: dict) -> dict:
    """Step 6: Validate, repair, or fallback the Layout JSON."""
    raw_json = ctx.get("step5", "{}")
    step4 = ctx.get("step4", {})
    input_json = ctx.get("input_json", {})
    asset_context = {
        "groups": step4.get("groups", []) if isinstance(step4, dict) else [],
        "input_image_urls": input_json.get("image_urls", []) if isinstance(input_json, dict) else [],
    }

    validator = LayoutValidator()
    repairer = LayoutRepairer()

    # Try to parse and repair
    repaired = repairer.repair(raw_json, [], asset_context=asset_context)
    if repaired is not None:
        errors = validator.validate(repaired)
        if not errors:
            return repaired
        logger.warning("step6_validation_errors", errors=errors)

    # If repair didn't fully fix, try re-repairing with errors list
    if repaired is not None:
        errors = validator.validate(repaired)
        repaired2 = repairer.repair(json.dumps(repaired, ensure_ascii=False), errors, asset_context=asset_context)
        if repaired2 is not None:
            errors2 = validator.validate(repaired2)
            if not errors2:
                return repaired2

    # Ultimate fallback
    emotion = ctx.get("step2", {}).get("primary_emotion", "neutral")
    content_text = input_json.get("text", "") or input_json.get("content_text", "")
    page_date = input_json.get("page_date", "")
    logger.warning(
        "step6_fallback_used",
        emotion=emotion,
        candidate_group_counts={group.get("material_type"): len(group.get("items", [])) for group in asset_context["groups"]},
        image_url_count=len(asset_context["input_image_urls"]),
    )
    fallback_layout = get_fallback_layout(emotion, content_text=content_text, page_date=page_date)
    repaired_fallback = repairer.repair(json.dumps(fallback_layout, ensure_ascii=False), [], asset_context=asset_context)
    if repaired_fallback is not None:
        return repaired_fallback
    return fallback_layout
