from __future__ import annotations

from typing import Any

from app.ai.layout_v2.enums import MaterialRole
from app.ai.layout_v2.schemas import MaterialCandidate, VisualBrief


def review_material_role_groups(
    *,
    brief: VisualBrief,
    role_groups: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    reviewed: dict[str, list[dict[str, Any]]] = {}
    rejected: list[dict[str, Any]] = []
    excluded = set(brief.excluded_concepts)
    for role_value, items in role_groups.items():
        try:
            role = MaterialRole(role_value)
        except ValueError:
            rejected.extend({"material_id": item.get("material_id"), "reason": "invalid_role_group"} for item in items)
            continue
        if role is MaterialRole.NONE:
            continue
        kept: list[dict[str, Any]] = []
        for raw in items:
            try:
                candidate = MaterialCandidate.model_validate(raw)
            except Exception as exc:
                rejected.append({"material_id": raw.get("material_id"), "role": role_value, "reason": f"invalid_candidate:{exc}"})
                continue
            if candidate.role is not role:
                rejected.append({"material_id": candidate.material_id, "role": role_value, "reason": "role_mismatch"})
                continue
            conflict = set(candidate.metadata.risk_flags).intersection(excluded)
            if conflict:
                rejected.append(
                    {
                        "material_id": candidate.material_id,
                        "role": role_value,
                        "reason": f"excluded_concept:{','.join(sorted(conflict))}",
                    }
                )
                continue
            kept.append(candidate.model_dump(mode="json"))
        reviewed[role_value] = kept
    return {"role_groups": reviewed, "rejected": rejected, "review_model": "metadata_v2"}
