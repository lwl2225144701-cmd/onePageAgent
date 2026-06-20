from __future__ import annotations

from typing import Any

from app.ai.layout_v2.catalog import list_templates
from app.ai.layout_v2.schemas import VisualBrief


def filter_templates(brief: VisualBrief, *, limit: int = 6) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for template in list_templates():
        score = template_fit_score(template, brief)
        if score > 0 or template["id"] == "minimal_text_only":
            scored.append((score, template))
    scored.sort(key=lambda item: (item[0], item[1]["id"] != "minimal_text_only"), reverse=True)
    result = [template for _, template in scored[: max(1, limit)]]
    if not any(template["id"] == "minimal_text_only" for template in result):
        result.append(next(template for _, template in scored if template["id"] == "minimal_text_only"))
    return result


def template_fit_score(template: dict[str, Any], brief: VisualBrief) -> float:
    length_score = 0.48 if brief.content_length in template["content_lengths"] else -0.6
    scene_values = {brief.scene, brief.sub_scene, "daily_life" if brief.scene in {"home", "outing"} else brief.scene}
    scene_score = 0.27 if scene_values.intersection(template["scenes"]) else 0.0
    tone_score = 0.15 if set(brief.preferred_color_tone).intersection(template["themes"]) else 0.0
    density_score = 0.10 if brief.preferred_density == template["density"] else 0.03
    if template["id"] == "minimal_text_only":
        return 0.24
    return round(length_score + scene_score + tone_score + density_score, 4)


def required_roles_for_templates(templates: list[dict[str, Any]]) -> set[str]:
    return {role for template in templates for role in template.get("required_roles", [])}
