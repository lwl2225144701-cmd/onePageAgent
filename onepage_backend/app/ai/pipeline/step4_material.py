from __future__ import annotations

import json


async def run_material_matching(ctx: dict) -> dict:
    from app.ai.layout_v2.catalog import public_template_summary
    from app.ai.layout_v2.material_retriever import retrieve_material_role_groups
    from app.ai.layout_v2.schemas import VisualBrief
    from app.ai.layout_v2.template_filter import filter_templates, required_roles_for_templates
    from app.ai.layout_v2.visual_brief import build_visual_brief_from_context

    brief = VisualBrief.model_validate(ctx.get("visual_brief") or build_visual_brief_from_context(ctx))
    templates = filter_templates(brief)
    required_roles = required_roles_for_templates(templates)
    input_json = ctx.get("input_json") if isinstance(ctx.get("input_json"), dict) else {}
    journal_context = ctx.get("journal_context") if isinstance(ctx.get("journal_context"), dict) else {}
    weather_context = journal_context.get("weather") if isinstance(journal_context.get("weather"), dict) else {}
    retrieved = await retrieve_material_role_groups(
        brief=brief,
        required_roles=required_roles,
        user_id=ctx.get("user_id"),
        user_text=str(input_json.get("text") or input_json.get("content_text") or ""),
        mood=str(input_json.get("mood") or ""),
        weather=str(weather_context.get("text") or weather_context.get("weather") or "unknown"),
        task_id=ctx.get("task_id"),
    )
    role_groups = retrieved["role_groups"]
    template_summaries = [public_template_summary(template) for template in templates]
    print(
        "ONEPAGE_TEMPLATE_CANDIDATES "
        f"task_id={ctx.get('task_id')} items={json.dumps([item['id'] for item in template_summaries], ensure_ascii=False)}",
        flush=True,
    )
    print(
        "ONEPAGE_MATERIAL_ROLE_CANDIDATES "
        f"task_id={ctx.get('task_id')} "
        f"counts={json.dumps({role: len(items) for role, items in role_groups.items()}, ensure_ascii=False)}",
        flush=True,
    )
    rejected = retrieved["rejected"]
    if rejected:
        reason_counts: dict[str, int] = {}
        for item in rejected:
            reason = str(item.get("reason") or "unknown").split(":", 1)[0]
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        print(
            "ONEPAGE_MATERIAL_REJECTED "
            f"task_id={ctx.get('task_id')} total={len(rejected)} "
            f"reasons={json.dumps(reason_counts, ensure_ascii=False)} "
            f"samples={json.dumps(rejected[:5], ensure_ascii=False)}",
            flush=True,
        )
    return {
        "summary": {
            "layout_engine": "v2",
            "visual_brief": brief.model_dump(mode="json"),
            "template_candidates": template_summaries,
            "required_roles": sorted(required_roles),
            "retrieval_plan": retrieved.get("retrieval_plan", {}),
        },
        "role_groups": role_groups,
        "rejected_materials": rejected,
    }
