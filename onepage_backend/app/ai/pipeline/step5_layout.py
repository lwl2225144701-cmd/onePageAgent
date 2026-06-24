from __future__ import annotations

import json

import structlog

from app.ai.gateway.deepseek_client import DeepSeekClient
from app.ai.layout_v2.catalog import get_template
from app.ai.layout_v2.compiler import compile_layout_v2
from app.ai.layout_v2.resolver import plan_log_summary, resolve_layout_plans
from app.ai.layout_v2.schemas import VisualBrief
from app.ai.layout_v2.visual_brief import build_visual_brief_from_context
from app.ai.pipeline.llm_json import extract_message_content
from app.ai.prompt_registry import LAYOUT_SELECTION_SYSTEM_PROMPT, build_layout_selection_prompt


logger = structlog.get_logger(__name__)


async def run_layout_generation(ctx: dict) -> str:
    task_id = str(ctx.get("task_id") or "")
    input_json = ctx.get("input_json") if isinstance(ctx.get("input_json"), dict) else {}
    content_text = str(input_json.get("text") or input_json.get("content_text") or "")
    review = ctx.get("step4_review") if isinstance(ctx.get("step4_review"), dict) else {}
    summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
    brief = VisualBrief.model_validate(ctx.get("visual_brief") or build_visual_brief_from_context(ctx))
    candidate_summaries = (
        summary.get("template_candidates") if isinstance(summary.get("template_candidates"), list) else []
    )
    templates = [
        get_template(str(item["id"]))
        for item in candidate_summaries
        if isinstance(item, dict) and item.get("id")
    ]
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
    prompt = build_layout_selection_prompt(brief, plans)
    try:
        raw = await _call_layout_model(prompt)
        decision = _parse_plan_decision(raw, plans, brief.title_hint)
        if decision:
            selected = next(plan for plan in plans if plan.template_id == decision["template_id"])
            selected = selected.model_copy(update={"title": decision["title"]})
            model_name = "deepseek"
    except Exception as exc:
        logger.warning("step5_layout_selection_failed", task_id=task_id, error=str(exc))

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
    ctx["step5_selected_materials"] = [
        item.model_dump(mode="json") for item in selected.materials.values()
    ]
    print(
        "ONEPAGE_LAYOUT_PLAN_SELECTED "
        f"task_id={task_id} model={model_name} plan={json.dumps(plan_log_summary(selected), ensure_ascii=False)}",
        flush=True,
    )
    print(
        "ONEPAGE_LAYOUT_V2_COMPILED "
        f"task_id={task_id} template_id={selected.template_id} "
        f"element_count={len(layout['elements'])} engine_version=2.0.0",
        flush=True,
    )
    return json.dumps(layout, ensure_ascii=False)


async def _call_layout_model(prompt: str) -> str | None:
    client = DeepSeekClient()
    try:
        response = await client.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=LAYOUT_SELECTION_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        return extract_message_content(response) or None
    finally:
        await client.close()


def _parse_plan_decision(raw: str | None, plans: list, title_hint: str) -> dict | None:
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
        "temperature": str(weather_context.get("temperature_celsius") or journal_context.get("temperature") or "").strip()
        if weather_success
        else "",
        "weather_success": weather_success,
        "location": location_context,
        "location_text": str(
            location_context.get("district")
            or location_context.get("city")
            or location_context.get("input_location")
            or ""
        ).strip(),
        "location_status": str(journal_context.get("location_status") or ""),
        "location_source": str(location_context.get("location_source") or ""),
        "source": journal_context.get("source"),
        "tool_success": bool(journal_context.get("tool_success")),
    }
