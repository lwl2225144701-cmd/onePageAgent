import json
import structlog

from app.ai.fallback.templates import get_fallback_layout
from app.ai.pipeline.llm_json import extract_message_content
from app.ai.prompts.layout_fewshots import (
    build_layout_policy,
    select_layout_fewshots,
    selected_material_bundle,
)
from app.ai.prompts.layout_generation import SYSTEM_PROMPT, USER_TEMPLATE

logger = structlog.get_logger(__name__)


async def run_layout_generation(ctx: dict) -> str:
    """Step 5: Generate Layout JSON via LLM."""
    step1 = ctx.get("step1", {})
    step2 = ctx.get("step2", {})
    step3 = ctx.get("step3", {})
    step4 = _layout_material_context(ctx.get("step4_review", {}))
    input_json = ctx["input_json"]
    print(f"STEP5_MODEL_START task_id={ctx.get('task_id')}", flush=True)
    counts = _reviewed_group_counts(step4)
    selected_materials = _select_materials_for_layout(step4)
    step4["selected_materials"] = selected_materials
    if isinstance(ctx.get("step4_review"), dict):
        ctx["step4_review"]["selected_materials"] = selected_materials
    ctx["step5_selected_materials"] = selected_materials
    material_bundle = selected_material_bundle(selected_materials)
    fewshot_candidates, fewshots = select_layout_fewshots(
        content_text=input_json.get("text", "") or input_json.get("content_text", ""),
        semantic=step1,
        style=step3,
        selected_materials=material_bundle,
        fallback_mode=str(step4.get("fallback_mode") or "none"),
    )
    print(
        "STEP5_REVIEWED_CANDIDATES "
        f"task_id={ctx.get('task_id')} "
        f"background={counts.get('background', 0)} "
        f"decoration={counts.get('decoration', 0)} "
        f"sticker={counts.get('sticker', 0)} "
        f"fallback_mode={step4.get('fallback_mode') if isinstance(step4, dict) else None}",
        flush=True,
    )
    print(
        "ONEPAGE_MATERIAL_SELECTED "
        f"task_id={ctx.get('task_id')} "
        f"items={json.dumps([_selected_material_log_item(item) for item in selected_materials], ensure_ascii=False)}",
        flush=True,
    )
    print(
        "ONEPAGE_FEWSHOT_CANDIDATES "
        f"task_id={ctx.get('task_id')} "
        f"items={json.dumps(fewshot_candidates, ensure_ascii=False)}",
        flush=True,
    )
    print(
        "ONEPAGE_FEWSHOT_SELECTED "
        f"task_id={ctx.get('task_id')} "
        f"examples={json.dumps([item['id'] for item in fewshots], ensure_ascii=False)}",
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
    text_analysis = step1.get("text_analysis", {}) if isinstance(step1.get("text_analysis"), dict) else {}
    layout_policy = build_layout_policy(
        content_text=content_text,
        title_hint=str(step1.get("topic") or text_analysis.get("topic") or ""),
        selected_materials=material_bundle,
    )
    prompt = _build_layout_prompt(
        content_text=content_text,
        image_info=image_info,
        style=step3,
        emotion_data=step2,
        materials=step4,
        selected_materials=material_bundle,
        layout_policy=layout_policy,
        weather=weather,
        mood=mood,
        page_date=page_date,
        authoritative_context=authoritative_context,
        fewshots=fewshots,
    )
    print(
        "ONEPAGE_LAYOUT_PROMPT_BUILT "
        f"task_id={ctx.get('task_id')} "
        f"fewshot_ids={json.dumps([item['id'] for item in fewshots], ensure_ascii=False)} "
        f"selected_material_ids={json.dumps([item.get('material_id') for item in selected_materials], ensure_ascii=False)} "
        f"content_length={len(content_text)} prompt_chars={len(prompt)}",
        flush=True,
    )
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
        result = await _call_qwen(prompt)
        if result:
            print(f"STEP5_MODEL_OK task_id={ctx.get('task_id')} model=qwen", flush=True)
            print(
                f"ONEPAGE_LAYOUT_GENERATED task_id={ctx.get('task_id')} model=qwen "
                f"bytes={len(result)} element_count={_generated_element_count(result)}",
                flush=True,
            )
            return result
    except Exception as e:
        logger.warning("step5_qwen_failed", error=str(e))

    # Try fallback model (DeepSeek)
    try:
        result = await _call_deepseek(prompt)
        if result:
            print(f"STEP5_MODEL_OK task_id={ctx.get('task_id')} model=deepseek", flush=True)
            print(
                f"ONEPAGE_LAYOUT_GENERATED task_id={ctx.get('task_id')} model=deepseek "
                f"bytes={len(result)} element_count={_generated_element_count(result)}",
                flush=True,
            )
            return result
    except Exception as e:
        logger.warning("step5_deepseek_failed", error=str(e))

    # Ultimate fallback
    emotion = step2.get("primary_emotion", "neutral")
    print(f"STEP5_MODEL_FALLBACK task_id={ctx.get('task_id')} emotion={emotion}", flush=True)
    fallback = json.dumps(get_fallback_layout(emotion, content_text=content_text, page_date=page_date), ensure_ascii=False)
    print(f"ONEPAGE_LAYOUT_GENERATED task_id={ctx.get('task_id')} model=fallback bytes={len(fallback)}", flush=True)
    return fallback


def _generated_element_count(raw_layout: str) -> int:
    try:
        parsed = json.loads(raw_layout)
    except (TypeError, json.JSONDecodeError):
        return 0
    elements = parsed.get("elements", []) if isinstance(parsed, dict) else []
    return len(elements) if isinstance(elements, list) else 0


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
        "rejected_materials": materials.get("rejected_materials", []),
    }


def _select_materials_for_layout(materials: dict) -> list[dict]:
    if not isinstance(materials, dict):
        return []
    fallback_mode = str(materials.get("fallback_mode") or "none")
    groups = materials.get("groups", []) if isinstance(materials.get("groups"), list) else []
    by_type: dict[str, list[dict]] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        material_type = str(group.get("material_type") or "")
        by_type[material_type] = [item for item in group.get("items", []) if isinstance(item, dict)]

    selected: list[dict] = []
    backgrounds = [item for item in by_type.get("background", []) if _usable_material(item, role="background")]
    selected.extend(_top_ranked(backgrounds, limit=1))
    stickers = _top_ranked([item for item in by_type.get("sticker", []) if _usable_material(item)], limit=3)
    if fallback_mode != "neutral_minimal":
        focal = [item for item in stickers if str(item.get("safe_role") or item.get("suggested_role") or "") == "focal_sticker"]
        selected.extend(focal[:1])
        supporting = [item for item in stickers if item not in focal]
        selected.extend(supporting[:2])
    else:
        supporting = [
            item
            for item in stickers
            if str(item.get("safe_role") or item.get("suggested_role") or "") != "focal_sticker"
        ]
        selected.extend(supporting[:1])
    decoration_limit = 2 if fallback_mode == "neutral_minimal" else 3
    selected.extend(_select_role_diverse_decorations(by_type.get("decoration", []), limit=decoration_limit))
    return _dedupe_materials(selected)


def _select_role_diverse_decorations(items: list[dict], *, limit: int) -> list[dict]:
    ranked = _top_ranked([item for item in items if _usable_material(item)], limit=max(limit * 3, limit))
    selected: list[dict] = []
    for desired_role in ("frame", "tape", "decoration"):
        match = next(
            (
                item
                for item in ranked
                if item not in selected
                and str(item.get("safe_role") or item.get("suggested_role") or "decoration") == desired_role
            ),
            None,
        )
        if match is not None:
            selected.append(match)
        if len(selected) >= limit:
            return selected
    selected.extend(item for item in ranked if item not in selected)
    return selected[:limit]


def _usable_material(item: dict, *, role: str = "") -> bool:
    if not isinstance(item, dict):
        return False
    if str(item.get("review_decision") or item.get("decision") or "keep") == "reject":
        return False
    material_id = str(item.get("material_id") or "").strip()
    url = str(item.get("file_url") or item.get("preview_url") or item.get("raw_file_url") or "").strip()
    if not material_id or not url or url.startswith(("/Users/", "/home/", "file://")):
        return False
    try:
        if item.get("asset_width") is not None and float(item["asset_width"]) <= 0:
            return False
        if item.get("asset_height") is not None and float(item["asset_height"]) <= 0:
            return False
    except (TypeError, ValueError):
        return False
    if role == "background" and item.get("background_safe") is False:
        return False
    return True


def _top_ranked(items: list[dict], *, limit: int) -> list[dict]:
    ranked = sorted(
        [item for item in items if isinstance(item, dict)],
        key=lambda item: (
            float(item.get("semantic_fit") or 0),
            float(item.get("visual_safety") or 0),
            float(item.get("score") or 0),
        ),
        reverse=True,
    )
    return ranked[:limit]


def _dedupe_materials(items: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for item in items:
        material_id = str(item.get("material_id") or item.get("file_url") or "")
        if not material_id or material_id in seen:
            continue
        seen.add(material_id)
        result.append(item)
    return result


def _selected_material_log_item(item: dict) -> dict:
    return {
        "material_id": item.get("material_id"),
        "role": item.get("safe_role") or item.get("suggested_role") or item.get("material_type"),
        "category": item.get("category"),
        "semantic_fit": item.get("semantic_fit"),
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


def _build_layout_prompt(
    *,
    content_text: str,
    image_info: str,
    style: dict,
    emotion_data: dict,
    materials: dict,
    selected_materials: dict,
    layout_policy: dict,
    weather: str,
    mood,
    page_date: str,
    authoritative_context: dict,
    fewshots: list[dict],
) -> str:
    return USER_TEMPLATE.format(
        content_text=content_text or "记录今日点滴",
        image_info=image_info,
        theme=style.get("theme", "healing"),
        font=style.get("font", "handwriting"),
        color_palette=json.dumps(style.get("color_palette", [])),
        layout_style=style.get("layout_style", "minimal"),
        emotion=json.dumps(emotion_data, ensure_ascii=False),
        recommended_materials=json.dumps(materials, ensure_ascii=False),
        authoritative_journal_context=json.dumps(authoritative_context, ensure_ascii=False),
        selected_materials=json.dumps(selected_materials, ensure_ascii=False),
        layout_policy=json.dumps(layout_policy, ensure_ascii=False),
        selected_fewshots=json.dumps(fewshots, ensure_ascii=False),
        weather=weather,
        mood=mood or "记录",
        page_date=page_date or "",
    )


async def _call_qwen(prompt: str) -> str | None:
    from app.ai.gateway.qwen_client import QwenClient
    return await _call_layout_model(
        client_factory=QwenClient,
        prompt=prompt,
    )


async def _call_deepseek(prompt: str) -> str | None:
    from app.ai.gateway.deepseek_client import DeepSeekClient
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
