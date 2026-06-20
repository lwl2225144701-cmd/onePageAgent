import json
import structlog

from app.ai.layout.compiler import compile_layout_template
from app.ai.pipeline.llm_json import extract_message_content
from app.ai.prompts.layout_fewshots import (
    content_length_bucket,
    select_layout_fewshots,
    selected_material_bundle,
)
from app.ai.prompts.layout_generation import SYSTEM_PROMPT, USER_TEMPLATE

logger = structlog.get_logger(__name__)


async def run_layout_generation(ctx: dict) -> str:
    """Select one template with the LLM, then compile deterministic Layout JSON."""
    from app.config import settings

    if settings.LAYOUT_ENGINE_VERSION == "v2":
        return await _run_layout_generation_v2(ctx)
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
    template_candidates, templates = select_layout_fewshots(
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
        f"items={json.dumps(template_candidates, ensure_ascii=False)}",
        flush=True,
    )
    print(
        "ONEPAGE_FEWSHOT_SELECTED "
        f"task_id={ctx.get('task_id')} "
        f"examples={json.dumps([item['id'] for item in templates], ensure_ascii=False)}",
        flush=True,
    )

    content_text = input_json.get("text", "") or input_json.get("content_text", "")
    journal_context = ctx.get("journal_context", {}) if isinstance(ctx.get("journal_context"), dict) else {}
    authoritative_context = build_authoritative_context(journal_context)
    mood = input_json.get("mood", step2.get("primary_emotion", ""))
    text_analysis = step1.get("text_analysis", {}) if isinstance(step1.get("text_analysis"), dict) else {}
    title_hint = str(step1.get("topic") or text_analysis.get("topic") or "今天的一页").strip() or "今天的一页"
    candidate_ids = [item["id"] for item in templates]
    default_template_id = candidate_ids[0]
    prompt = _build_layout_prompt(
        content_text=content_text,
        title_hint=title_hint,
        style=step3,
        emotion_data=step2,
        selected_materials=material_bundle,
        semantic=step1,
        templates=templates,
    )
    print(
        "ONEPAGE_LAYOUT_PROMPT_BUILT "
        f"task_id={ctx.get('task_id')} "
        f"fewshot_ids={json.dumps(candidate_ids, ensure_ascii=False)} "
        f"selected_material_ids={json.dumps([item.get('material_id') for item in selected_materials], ensure_ascii=False)} "
        f"content_length={len(content_text)} prompt_chars={len(prompt)}",
        flush=True,
    )
    print(
        "STEP5_AUTHORITATIVE_CONTEXT "
        f"task_id={ctx.get('task_id')} "
        f"date={authoritative_context['date_text']} "
        f"weather={authoritative_context['weather_text'] or 'unknown'} "
        f"weather_icon={authoritative_context['weather_icon'] or ''}",
        flush=True,
    )

    decision = None
    model_name = "deterministic"
    for name, caller in (("qwen", _call_qwen), ("deepseek", _call_deepseek)):
        try:
            raw_decision = await caller(prompt)
            decision = _parse_layout_decision(raw_decision, candidate_ids=candidate_ids, content_text=content_text, title_hint=title_hint)
            if decision:
                model_name = name
                print(f"STEP5_MODEL_OK task_id={ctx.get('task_id')} model={name}", flush=True)
                break
        except Exception as exc:
            logger.warning(f"step5_{name}_failed", error=str(exc))

    if decision is None:
        decision = _default_layout_decision(default_template_id, content_text=content_text, title_hint=title_hint)
        print(f"STEP5_MODEL_FALLBACK task_id={ctx.get('task_id')} template_id={default_template_id}", flush=True)

    print(
        "ONEPAGE_TEMPLATE_SELECTED "
        f"task_id={ctx.get('task_id')} template_id={decision['template_id']} model={model_name}",
        flush=True,
    )
    layout = compile_layout_template(
        template_id=decision["template_id"],
        title=decision["title"],
        body=decision["body"],
        mood=mood,
        authoritative_context=authoritative_context,
        selected_materials=material_bundle,
        style=step3,
        optional_slots=decision["optional_slots"],
    )
    ctx["step5_template_id"] = decision["template_id"]
    ctx["step5_decision"] = decision
    compiled = json.dumps(layout, ensure_ascii=False)
    print(
        "ONEPAGE_TEMPLATE_COMPILED "
        f"task_id={ctx.get('task_id')} template_id={decision['template_id']} element_count={len(layout['elements'])}",
        flush=True,
    )
    print(
        "ONEPAGE_LAYOUT_GENERATED "
        f"task_id={ctx.get('task_id')} model={model_name} template_id={decision['template_id']} "
        f"bytes={len(compiled)} element_count={len(layout['elements'])}",
        flush=True,
    )
    return compiled


async def _run_layout_generation_v2(ctx: dict) -> str:
    from app.ai.layout_v2.catalog import get_template
    from app.ai.layout_v2.compiler import compile_layout_v2
    from app.ai.layout_v2.prompt import SYSTEM_PROMPT as V2_SYSTEM_PROMPT
    from app.ai.layout_v2.prompt import build_plan_selection_prompt
    from app.ai.layout_v2.resolver import plan_log_summary, resolve_layout_plans
    from app.ai.layout_v2.schemas import VisualBrief
    from app.ai.layout_v2.visual_brief import build_visual_brief_from_context

    task_id = str(ctx.get("task_id") or "")
    input_json = ctx.get("input_json") if isinstance(ctx.get("input_json"), dict) else {}
    content_text = str(input_json.get("text") or input_json.get("content_text") or "")
    review = ctx.get("step4_review") if isinstance(ctx.get("step4_review"), dict) else {}
    summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
    brief = VisualBrief.model_validate(ctx.get("visual_brief") or build_visual_brief_from_context(ctx))
    candidate_summaries = summary.get("template_candidates") if isinstance(summary.get("template_candidates"), list) else []
    templates = [get_template(str(item["id"])) for item in candidate_summaries if isinstance(item, dict) and item.get("id")]
    if not templates:
        from app.ai.layout_v2.template_filter import filter_templates

        templates = filter_templates(brief)
    role_groups = review.get("role_groups") if isinstance(review.get("role_groups"), dict) else {}
    plans = resolve_layout_plans(brief, templates, role_groups, limit=4)
    print(
        "ONEPAGE_LAYOUT_COMBINATIONS "
        f"task_id={task_id} items={json.dumps([plan_log_summary(plan) for plan in plans], ensure_ascii=False)}",
        flush=True,
    )

    selected = plans[0]
    model_name = "resolver"
    prompt = build_plan_selection_prompt(brief, plans)
    for name, caller in (("qwen", _call_qwen_v2), ("deepseek", _call_deepseek_v2)):
        try:
            raw = await caller(prompt, V2_SYSTEM_PROMPT)
            decision = _parse_v2_plan_decision(raw, plans, brief.title_hint)
            if decision:
                selected = next(plan for plan in plans if plan.template_id == decision["template_id"])
                selected = selected.model_copy(update={"title": decision["title"]})
                model_name = name
                break
        except Exception as exc:
            logger.warning(f"step5_v2_{name}_failed", task_id=task_id, error=str(exc))

    authoritative_context = build_authoritative_context(
        ctx.get("journal_context") if isinstance(ctx.get("journal_context"), dict) else {}
    )
    layout = compile_layout_v2(
        plan=selected,
        visual_brief=brief,
        authoritative_context=authoritative_context,
        mood=input_json.get("mood", ""),
        task_id=task_id,
        content_text=content_text,
    )
    ctx["layout_v2_plan"] = selected.model_dump(mode="json")
    ctx["layout_v2_authoritative_context"] = authoritative_context
    ctx["step5_template_id"] = selected.template_id
    ctx["step5_selected_materials"] = [item.model_dump(mode="json") for item in selected.materials.values()]
    print(
        "ONEPAGE_LAYOUT_PLAN_SELECTED "
        f"task_id={task_id} model={model_name} plan={json.dumps(plan_log_summary(selected), ensure_ascii=False)}",
        flush=True,
    )
    print(
        "ONEPAGE_LAYOUT_V2_COMPILED "
        f"task_id={task_id} template_id={selected.template_id} element_count={len(layout['elements'])} engine_version=2.0.0",
        flush=True,
    )
    return json.dumps(layout, ensure_ascii=False)


def _parse_v2_plan_decision(raw: str | None, plans: list, title_hint: str) -> dict | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    candidate_ids = {plan.template_id for plan in plans}
    template_id = str(payload.get("template_id") or "") if isinstance(payload, dict) else ""
    if template_id not in candidate_ids:
        return None
    title = str(payload.get("title") or title_hint or "今天的一页").strip()[:40] or "今天的一页"
    return {"template_id": template_id, "title": title}


async def _call_qwen_v2(prompt: str, system_prompt: str) -> str | None:
    from app.ai.gateway.qwen_client import QwenClient

    return await _call_layout_model_v2(QwenClient, prompt, system_prompt)


async def _call_deepseek_v2(prompt: str, system_prompt: str) -> str | None:
    from app.ai.gateway.deepseek_client import DeepSeekClient

    return await _call_layout_model_v2(DeepSeekClient, prompt, system_prompt)


async def _call_layout_model_v2(client_factory, prompt: str, system_prompt: str) -> str | None:
    client = client_factory()
    try:
        response = await client.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        return extract_message_content(response) or None
    finally:
        await client.close()


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
    title_hint: str,
    style: dict,
    emotion_data: dict,
    selected_materials: dict,
    semantic: dict,
    templates: list[dict],
) -> str:
    return USER_TEMPLATE.format(
        content_text=content_text or "记录今日点滴",
        title_hint=title_hint,
        theme=style.get("theme", "healing"),
        emotion=json.dumps(emotion_data, ensure_ascii=False),
        semantic=json.dumps(semantic, ensure_ascii=False),
        content_length=content_length_bucket(content_text),
        available_roles=json.dumps([role for role, value in selected_materials.items() if value], ensure_ascii=False),
        template_candidates=json.dumps(templates, ensure_ascii=False),
    )


def _parse_layout_decision(
    raw: str | None,
    *,
    candidate_ids: list[str],
    content_text: str,
    title_hint: str,
) -> dict | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict) or str(payload.get("template_id") or "") not in candidate_ids:
        return None
    optional = payload.get("optional_slots") if isinstance(payload.get("optional_slots"), dict) else {}
    allowed_slots = {"background", "focal_sticker", "supporting_sticker", "tape", "decoration", "frame"}
    return {
        "template_id": str(payload["template_id"]),
        "title": str(payload.get("title") or title_hint or "今天的一页").strip()[:40] or "今天的一页",
        "body": str(payload.get("body") or content_text).strip() or content_text,
        "optional_slots": {
            key: value
            for key, value in optional.items()
            if key in allowed_slots and isinstance(value, bool)
        },
    }


def _default_layout_decision(template_id: str, *, content_text: str, title_hint: str) -> dict:
    return {
        "template_id": template_id,
        "title": title_hint[:40] or "今天的一页",
        "body": content_text or "记录今日点滴",
        "optional_slots": {},
    }


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
            temperature=0.2,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        content = extract_message_content(response)
        return content or None
    finally:
        await client.close()
