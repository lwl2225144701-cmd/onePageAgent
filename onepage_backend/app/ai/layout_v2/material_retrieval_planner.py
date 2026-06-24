from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway.local_ollama_text_client import LocalOllamaTextClient
from app.ai.layout_v2.material_plan_cache import (
    build_material_plan_cache_key,
    cache_material_plan,
    get_cached_material_plan,
)
from app.ai.layout_v2.material_retrieval_plan import (
    DEFAULT_EXCLUDE_RISKS,
    MaterialRetrievalPlan,
    MaterialRetrievalWhitelist,
    build_deterministic_fallback_plan,
    normalize_material_retrieval_plan,
)
from app.ai.prompt_registry import (
    MATERIAL_RETRIEVAL_SYSTEM_PROMPT,
    build_material_retrieval_prompt,
    parse_material_retrieval_plan,
    select_material_retrieval_fewshots,
)
from app.ai.layout_v2.schemas import VisualBrief
from app.config import settings


async def load_material_retrieval_whitelist(db: AsyncSession) -> MaterialRetrievalWhitelist:
    rows = (
        await db.execute(
            text(
                """
                SELECT 'category' AS kind, meta_info ->> 'category' AS value
                FROM materials
                WHERE COALESCE(meta_info ->> 'annotation_version', '') = 'v2'
                UNION
                SELECT 'sub_category' AS kind, meta_info ->> 'sub_category' AS value
                FROM materials
                WHERE COALESCE(meta_info ->> 'annotation_version', '') = 'v2'
                UNION
                SELECT 'style' AS kind, style.value
                FROM materials AS m
                CROSS JOIN LATERAL jsonb_array_elements_text(
                    COALESCE(CAST(m.style_tags AS jsonb), '[]'::jsonb)
                ) AS style(value)
                UNION
                SELECT 'style' AS kind, meta_info ->> 'visual_style' AS value
                FROM materials
                WHERE COALESCE(meta_info ->> 'annotation_version', '') = 'v2'
                """
            )
        )
    ).all()
    values: dict[str, set[str]] = {"category": set(), "sub_category": set(), "style": set()}
    for kind, value in rows:
        normalized = str(value or "").strip()
        if kind in values and normalized:
            values[kind].add(normalized)
    return MaterialRetrievalWhitelist(
        categories=sorted(values["category"]),
        sub_categories=sorted(values["sub_category"]),
        styles=sorted(values["style"]),
        risk_flags=DEFAULT_EXCLUDE_RISKS,
    )


async def create_material_retrieval_plan(
    *,
    visual_brief: VisualBrief,
    user_text: str,
    mood: str,
    weather: str,
    whitelist: MaterialRetrievalWhitelist,
    task_id: str | None,
) -> MaterialRetrievalPlan:
    cache_key = build_material_plan_cache_key(
        visual_brief=visual_brief,
        whitelist=whitelist,
        mood=mood,
        weather=weather,
    )
    cached = await get_cached_material_plan(cache_key=cache_key, task_id=task_id)
    if cached is not None:
        return cached

    fewshot_limit = max(1, min(int(settings.MATERIAL_PLAN_MAX_FEWSHOTS or 2), 3))
    selected_fewshots = select_material_retrieval_fewshots(
        visual_brief=visual_brief,
        user_text=user_text,
        limit=fewshot_limit,
    )
    prompt = build_material_retrieval_prompt(
        user_text=user_text,
        mood=mood,
        weather=weather,
        visual_brief=visual_brief,
        allowed_roles=whitelist.roles,
        allowed_categories=whitelist.categories,
        allowed_sub_categories=whitelist.sub_categories,
        allowed_styles=whitelist.styles,
        fewshot_limit=fewshot_limit,
    )
    print(
        "ONEPAGE_MATERIAL_PLAN_START "
        f"task_id={task_id} model={settings.LOCAL_TEXT_LLM_MODEL} prompt_chars={len(prompt)} "
        f"fewshots={json.dumps([item['name'] for item in selected_fewshots], ensure_ascii=False)}",
        flush=True,
    )
    client = LocalOllamaTextClient()
    raw_plan: dict[str, Any] = {}
    try:
        response = await client.generate_json(
            prompt=prompt,
            system_prompt=MATERIAL_RETRIEVAL_SYSTEM_PROMPT,
            task_id=task_id,
        )
        raw_plan = parse_material_retrieval_plan(response.get("content", ""))
        normalized = normalize_material_retrieval_plan(
            raw_plan,
            visual_brief=visual_brief,
            whitelist=whitelist,
        )
        print(
            "ONEPAGE_MATERIAL_PLAN_GENERATED "
            f"task_id={task_id} elapsed_ms={response.get('elapsed_ms')} groups={len(normalized.groups)}",
            flush=True,
        )
        print(
            "ONEPAGE_MATERIAL_PLAN_NORMALIZED "
            f"task_id={task_id} source={normalized.source} roles={json.dumps([item.role for item in normalized.groups])}",
            flush=True,
        )
        await cache_material_plan(
            cache_key=cache_key,
            raw_plan=raw_plan,
            normalized_plan=normalized,
            task_id=task_id,
        )
        return normalized
    except Exception as exc:
        fallback = build_deterministic_fallback_plan(visual_brief=visual_brief, whitelist=whitelist)
        print(
            "ONEPAGE_MATERIAL_PLAN_FALLBACK "
            f"task_id={task_id} reason={str(exc)[:160]} roles={json.dumps([item.role for item in fallback.groups])}",
            flush=True,
        )
        return fallback
    finally:
        await client.close()
