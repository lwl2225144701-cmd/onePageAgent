from __future__ import annotations

import json


async def run_validate_and_repair(ctx: dict) -> dict:
    raw_json = ctx.get("step5", "{}")
    return _validate_or_fallback_v2(ctx, raw_json)


def _validate_or_fallback_v2(ctx: dict, raw_json: str) -> dict:
    from app.ai.layout_v2.catalog import get_template
    from app.ai.layout_v2.compiler import compile_layout_v2
    from app.ai.layout_v2.material_binder import bind_materials_for_template
    from app.ai.layout_v2.schemas import LayoutPlan, VisualBrief
    from app.ai.layout_v2.validator import validate_layout_v2
    from app.ai.layout_v2.visual_brief import build_visual_brief_from_context

    task_id = str(ctx.get("task_id") or "")
    layout = json.loads(raw_json)
    plan = LayoutPlan.model_validate(ctx.get("layout_v2_plan"))
    brief = VisualBrief.model_validate(ctx.get("visual_brief") or build_visual_brief_from_context(ctx))
    authoritative_context = ctx.get("layout_v2_authoritative_context")
    authoritative_context = authoritative_context if isinstance(authoritative_context, dict) else {}
    errors = validate_layout_v2(layout, plan=plan, authoritative_context=authoritative_context)
    print(
        "ONEPAGE_LAYOUT_V2_VALIDATED "
        f"task_id={task_id} template_id={plan.template_id} pass={str(not errors).lower()} "
        f"errors={json.dumps(errors, ensure_ascii=False)}",
        flush=True,
    )
    if not errors:
        return layout

    review = ctx.get("step4_review") if isinstance(ctx.get("step4_review"), dict) else {}
    role_groups = review.get("role_groups") if isinstance(review.get("role_groups"), dict) else {}
    input_json = ctx.get("input_json") if isinstance(ctx.get("input_json"), dict) else {}
    content_text = str(input_json.get("text") or input_json.get("content_text") or "")
    fallback_id = get_template(plan.template_id).get("fallback_template")
    visited = {plan.template_id}
    while fallback_id and fallback_id not in visited:
        visited.add(fallback_id)
        template = get_template(fallback_id)
        bundle = bind_materials_for_template(template=template, visual_brief=brief, role_groups=role_groups)
        if bundle["satisfies_required_roles"]:
            fallback_plan = LayoutPlan(
                template_id=fallback_id,
                materials=bundle["materials"],
                title=plan.title,
                score=0,
                fallback_reason=f"validator:{','.join(errors)}",
            )
            fallback_layout = compile_layout_v2(
                plan=fallback_plan,
                visual_brief=brief,
                authoritative_context=authoritative_context,
                mood=input_json.get("mood", ""),
                task_id=task_id,
                content_text=content_text,
            )
            fallback_errors = validate_layout_v2(
                fallback_layout,
                plan=fallback_plan,
                authoritative_context=authoritative_context,
            )
            print(
                "ONEPAGE_LAYOUT_V2_FALLBACK "
                f"task_id={task_id} from_template={plan.template_id} to_template={fallback_id} "
                f"reason={json.dumps(errors, ensure_ascii=False)} pass={str(not fallback_errors).lower()}",
                flush=True,
            )
            if not fallback_errors:
                ctx["layout_v2_plan"] = fallback_plan.model_dump(mode="json")
                return fallback_layout
        fallback_id = template.get("fallback_template")
    raise ValueError(f"layout_v2_validation_failed:{errors}")
