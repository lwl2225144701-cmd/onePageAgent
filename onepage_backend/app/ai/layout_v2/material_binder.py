from __future__ import annotations

from typing import Any

from app.ai.layout_v2.schemas import MaterialCandidate, VisualBrief


def bind_materials_for_template(
    *,
    template: dict[str, Any],
    visual_brief: VisualBrief,
    role_groups: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    bound: dict[str, MaterialCandidate] = {}
    missing: list[str] = []
    used_ids: set[str] = set()
    for role in template.get("required_roles", []):
        candidates: list[MaterialCandidate] = []
        for raw in role_groups.get(role, []):
            try:
                candidate = MaterialCandidate.model_validate(raw)
            except Exception:
                continue
            if candidate.role.value != role or candidate.material_id in used_ids:
                continue
            candidates.append(candidate)
        candidates.sort(key=lambda item: item.total_score, reverse=True)
        if not candidates:
            missing.append(role)
            continue
        selected = candidates[0]
        bound[role] = selected
        used_ids.add(selected.material_id)

    complete = not missing
    semantic_score = sum(item.semantic_score for item in bound.values()) / max(1, len(bound))
    coherence_score = _visual_coherence(list(bound.values()), visual_brief)
    return {
        "materials": bound,
        "satisfies_required_roles": complete,
        "missing_roles": missing,
        "material_semantic_score": round(semantic_score, 4),
        "visual_coherence_score": round(coherence_score, 4),
        "role_completeness_score": 1.0 if complete else len(bound) / max(1, len(template.get("required_roles", []))),
    }


def _visual_coherence(materials: list[MaterialCandidate], brief: VisualBrief) -> float:
    if not materials:
        return 1.0
    tones = [item.metadata.color_tone for item in materials if item.metadata.color_tone]
    styles = [item.metadata.visual_style for item in materials if item.metadata.visual_style]
    tone_score = _dominant_ratio(tones)
    style_score = _dominant_ratio(styles)
    preferred = {item.lower() for item in brief.preferred_color_tone}
    preferred_hits = sum(1 for item in [*tones, *styles] if item.lower() in preferred)
    preferred_score = preferred_hits / max(1, len(tones) + len(styles))
    return min(1.0, 0.4 * tone_score + 0.4 * style_score + 0.2 * preferred_score)


def _dominant_ratio(values: list[str]) -> float:
    if not values:
        return 0.7
    counts: dict[str, int] = {}
    for value in values:
        key = value.lower()
        counts[key] = counts.get(key, 0) + 1
    return max(counts.values()) / len(values)
