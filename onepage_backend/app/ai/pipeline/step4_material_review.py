from __future__ import annotations


async def run_material_review(ctx: dict) -> dict:
    from app.ai.layout_v2.material_reviewer import review_material_role_groups
    from app.ai.layout_v2.schemas import VisualBrief
    from app.ai.layout_v2.visual_brief import build_visual_brief_from_context

    task_id = ctx.get("task_id")
    step4 = ctx.get("step4") if isinstance(ctx.get("step4"), dict) else {}
    brief = VisualBrief.model_validate(ctx.get("visual_brief") or build_visual_brief_from_context(ctx))
    role_groups = step4.get("role_groups") if isinstance(step4.get("role_groups"), dict) else {}
    result = review_material_role_groups(brief=brief, role_groups=role_groups)
    rejected = [*(step4.get("rejected_materials") or []), *result["rejected"]]
    reviewed = result["role_groups"]
    print(
        "STEP4_REVIEW_RESULT "
        f"task_id={task_id} kept={sum(len(items) for items in reviewed.values())} "
        f"rejected={len(rejected)} fallback_mode=resolver model={result['review_model']} vision_failed=False",
        flush=True,
    )
    return {
        "summary": step4.get("summary", {}),
        "role_groups": reviewed,
        "rejected_materials": rejected,
        "review_summary": {
            "kept_count": sum(len(items) for items in reviewed.values()),
            "rejected_count": len(rejected),
            "model_used": result["review_model"],
            "vision_failed": False,
        },
    }
