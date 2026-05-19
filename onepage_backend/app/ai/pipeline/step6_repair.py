import json
import structlog

from app.ai.fallback.repairer import LayoutRepairer
from app.ai.fallback.templates import get_fallback_layout
from app.ai.fallback.validator import LayoutValidator

logger = structlog.get_logger(__name__)


async def run_validate_and_repair(ctx: dict) -> dict:
    """Step 6: Validate, repair, or fallback the Layout JSON."""
    raw_json = ctx.get("step5", "{}")

    validator = LayoutValidator()
    repairer = LayoutRepairer()

    # Try to parse and repair
    repaired = repairer.repair(raw_json, [])
    if repaired is not None:
        errors = validator.validate(repaired)
        if not errors:
            return repaired
        logger.warning("step6_validation_errors", errors=errors)

    # If repair didn't fully fix, try re-repairing with errors list
    if repaired is not None:
        errors = validator.validate(repaired)
        repaired2 = repairer.repair(json.dumps(repaired, ensure_ascii=False), errors)
        if repaired2 is not None:
            errors2 = validator.validate(repaired2)
            if not errors2:
                return repaired2

    # Ultimate fallback
    emotion = ctx.get("step2", {}).get("primary_emotion", "neutral")
    logger.warning("step6_fallback_used", emotion=emotion)
    return get_fallback_layout(emotion)
