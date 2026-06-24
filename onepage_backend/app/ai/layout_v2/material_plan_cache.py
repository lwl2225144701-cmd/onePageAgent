from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.ai.layout_v2.material_retrieval_plan import MaterialRetrievalPlan, MaterialRetrievalWhitelist
from app.ai.prompt_registry import MATERIAL_RETRIEVAL_PROMPT_VERSION
from app.ai.layout_v2.schemas import VisualBrief
from app.config import settings
from app.core.redis import get_redis


def build_material_plan_cache_key(
    *,
    visual_brief: VisualBrief,
    whitelist: MaterialRetrievalWhitelist,
    mood: str,
    weather: str,
) -> str:
    signature = {
        "prompt_version": MATERIAL_RETRIEVAL_PROMPT_VERSION,
        "scene": visual_brief.scene,
        "sub_scene": visual_brief.sub_scene,
        "content_length": visual_brief.content_length,
        "required_concepts": sorted(visual_brief.required_concepts),
        "objects": sorted(visual_brief.objects),
        "mood": str(mood or "").strip(),
        "weather": str(weather or "").strip(),
        "taxonomy": whitelist.model_dump(mode="json"),
    }
    digest = hashlib.sha256(json.dumps(signature, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return f"onepage:material-plan:{digest}"


async def get_cached_material_plan(*, cache_key: str, task_id: str | None) -> MaterialRetrievalPlan | None:
    try:
        redis = await get_redis()
        raw = await redis.get(cache_key)
        if not raw:
            print(f"ONEPAGE_MATERIAL_PLAN_CACHE_MISS task_id={task_id}", flush=True)
            return None
        payload = json.loads(raw)
        plan = MaterialRetrievalPlan.model_validate(payload.get("normalized_plan"))
        plan.source = "cache"
        print(f"ONEPAGE_MATERIAL_PLAN_CACHE_HIT task_id={task_id}", flush=True)
        return plan
    except Exception as exc:
        print(f"ONEPAGE_MATERIAL_PLAN_CACHE_MISS task_id={task_id} reason={str(exc)[:120]}", flush=True)
        return None


async def cache_material_plan(
    *,
    cache_key: str,
    raw_plan: dict[str, Any],
    normalized_plan: MaterialRetrievalPlan,
    task_id: str | None,
) -> None:
    try:
        redis = await get_redis()
        payload = {
            "raw_plan": raw_plan,
            "normalized_plan": normalized_plan.model_dump(mode="json"),
            "created_at": datetime.now(UTC).isoformat(),
        }
        await redis.setex(
            cache_key,
            max(1, int(settings.MATERIAL_PLAN_CACHE_TTL_SECONDS or 1800)),
            json.dumps(payload, ensure_ascii=False),
        )
    except Exception as exc:
        print(f"ONEPAGE_MATERIAL_PLAN_CACHE_WRITE_FAILED task_id={task_id} reason={str(exc)[:120]}", flush=True)
