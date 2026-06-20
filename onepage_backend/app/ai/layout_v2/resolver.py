from __future__ import annotations

from typing import Any

from app.ai.layout_v2.material_binder import bind_materials_for_template
from app.ai.layout_v2.schemas import LayoutPlan, VisualBrief
from app.ai.layout_v2.template_filter import template_fit_score


def resolve_layout_plans(
    visual_brief: VisualBrief,
    template_catalog: list[dict[str, Any]],
    material_role_groups: dict[str, list[dict[str, Any]]],
    *,
    limit: int = 4,
) -> list[LayoutPlan]:
    plans: list[LayoutPlan] = []
    for template in template_catalog:
        bundle = bind_materials_for_template(
            template=template,
            visual_brief=visual_brief,
            role_groups=material_role_groups,
        )
        if not bundle["satisfies_required_roles"]:
            continue
        template_score = template_fit_score(template, visual_brief)
        role_score = float(bundle["role_completeness_score"])
        material_score = float(bundle["material_semantic_score"])
        coherence_score = float(bundle["visual_coherence_score"])
        score = 0.36 * template_score + 0.34 * material_score + 0.18 * coherence_score + 0.12 * role_score
        if template["id"] == "minimal_text_only":
            score = max(score, 0.24)
        plans.append(
            LayoutPlan(
                template_id=template["id"],
                materials=bundle["materials"],
                title=visual_brief.title_hint,
                score=round(score, 4),
                fallback_reason="" if template["required_roles"] else "no_material_required",
            )
        )
    plans.sort(key=lambda plan: (plan.score, plan.template_id != "minimal_text_only"), reverse=True)
    if not plans:
        raise RuntimeError("layout_v2_no_valid_plan")
    return plans[: max(1, limit)]


def resolve_layout_plan(
    visual_brief: VisualBrief,
    template_catalog: list[dict[str, Any]],
    material_role_groups: dict[str, list[dict[str, Any]]],
) -> LayoutPlan:
    return resolve_layout_plans(visual_brief, template_catalog, material_role_groups, limit=1)[0]


def plan_log_summary(plan: LayoutPlan) -> dict[str, Any]:
    return {
        "template_id": plan.template_id,
        "score": plan.score,
        "materials": {role: material.material_id for role, material in plan.materials.items()},
        "fallback_reason": plan.fallback_reason,
    }
