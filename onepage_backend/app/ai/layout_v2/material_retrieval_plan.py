from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.layout_v2.schemas import VisualBrief


DEFAULT_EXCLUDE_RISKS = [
    "valentine",
    "wedding",
    "romance",
    "festival_text",
    "medical",
    "sick",
    "wheelchair",
    "elderly_care",
    "religion",
    "business_sales",
    "party",
]

ROLE_DEFAULTS: dict[str, dict[str, Any]] = {
    "focal_sticker": {
        "material_types": ["sticker"],
        "suggested_roles": ["focal_sticker"],
        "limit": 20,
        "density": ["low", "medium"],
        "background_safe": False,
    },
    "supporting_sticker": {
        "material_types": ["sticker"],
        "suggested_roles": ["supporting_sticker"],
        "limit": 8,
        "density": ["low", "medium"],
        "background_safe": False,
    },
    "background": {
        "material_types": ["background"],
        "suggested_roles": ["background"],
        "limit": 10,
        "density": ["low", "medium"],
        "background_safe": True,
    },
    "tape": {
        "material_types": ["decoration"],
        "suggested_roles": ["tape"],
        "limit": 8,
        "density": ["low", "medium"],
        "background_safe": False,
    },
    "frame": {
        "material_types": ["decoration"],
        "suggested_roles": ["frame"],
        "limit": 8,
        "density": ["low", "medium"],
        "background_safe": False,
    },
    "decoration": {
        "material_types": ["decoration"],
        "suggested_roles": ["decoration"],
        "limit": 8,
        "density": ["low", "medium"],
        "background_safe": False,
    },
}


class MaterialRetrievalWhitelist(BaseModel):
    model_config = ConfigDict(extra="ignore")

    roles: list[str] = Field(default_factory=lambda: list(ROLE_DEFAULTS))
    material_types: list[str] = Field(default_factory=lambda: ["background", "sticker", "decoration"])
    categories: list[str] = Field(default_factory=list)
    sub_categories: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUDE_RISKS))


class MaterialRetrievalGroup(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    material_types: list[str]
    categories: list[str] = Field(default_factory=list)
    sub_categories: list[str] = Field(default_factory=list)
    suggested_roles: list[str]
    styles: list[str] = Field(default_factory=list)
    query_terms: list[str] = Field(default_factory=list)
    exclude_risks: list[str] = Field(default_factory=list)
    background_safe: bool = False
    density: list[str] = Field(default_factory=list)
    limit: int
    fallback_terms: list[str] = Field(default_factory=list)


class MaterialRetrievalPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scene: str
    sub_scene: str
    strategy: str = "progressive"
    groups: list[MaterialRetrievalGroup] = Field(default_factory=list)
    source: str = "model"


def normalize_material_retrieval_plan(
    raw_plan: dict[str, Any] | None,
    *,
    visual_brief: VisualBrief,
    whitelist: MaterialRetrievalWhitelist,
) -> MaterialRetrievalPlan:
    payload = raw_plan if isinstance(raw_plan, dict) else {}
    allowed_roles = set(whitelist.roles).intersection(ROLE_DEFAULTS)
    allowed_categories = set(whitelist.categories)
    allowed_sub_categories = set(whitelist.sub_categories)
    allowed_styles = set(whitelist.styles)
    allowed_risks = set(whitelist.risk_flags)
    default_terms = _dedupe([*visual_brief.required_concepts, *visual_brief.visual_keywords, *visual_brief.objects])
    risks = [item for item in _dedupe([*DEFAULT_EXCLUDE_RISKS, *visual_brief.excluded_concepts]) if item in allowed_risks]
    groups: list[MaterialRetrievalGroup] = []
    seen_roles: set[str] = set()
    for raw_group in payload.get("groups", []) if isinstance(payload.get("groups"), list) else []:
        if not isinstance(raw_group, dict):
            continue
        role = str(raw_group.get("role") or "").strip()
        if role not in allowed_roles or role in seen_roles:
            continue
        categories = _allowlisted(raw_group.get("categories"), allowed_categories)
        sub_categories = _allowlisted(raw_group.get("sub_categories"), allowed_sub_categories)
        styles = _allowlisted(raw_group.get("styles"), allowed_styles)
        query_terms = _terms(raw_group.get("query_terms")) or default_terms[:8]
        if not categories and not query_terms:
            continue
        defaults = ROLE_DEFAULTS[role]
        fallback_terms = _dedupe([*query_terms[1:], *sub_categories, *categories])[:8]
        groups.append(
            MaterialRetrievalGroup(
                role=role,
                material_types=defaults["material_types"],
                categories=categories,
                sub_categories=sub_categories,
                suggested_roles=defaults["suggested_roles"],
                styles=styles,
                query_terms=query_terms[:8],
                exclude_risks=risks,
                background_safe=defaults["background_safe"],
                density=defaults["density"],
                limit=defaults["limit"],
                fallback_terms=fallback_terms,
            )
        )
        seen_roles.add(role)
        if len(groups) >= 3:
            break
    strategy = str(payload.get("strategy") or "progressive").strip()
    if strategy not in {"strict", "progressive", "minimal"}:
        strategy = "progressive"
    if not groups:
        return build_deterministic_fallback_plan(visual_brief=visual_brief, whitelist=whitelist)
    return MaterialRetrievalPlan(
        scene=str(payload.get("scene") or visual_brief.scene).strip()[:64],
        sub_scene=str(payload.get("sub_scene") or visual_brief.sub_scene).strip()[:64],
        strategy=strategy,
        groups=groups,
        source="model",
    )


def build_deterministic_fallback_plan(
    *,
    visual_brief: VisualBrief,
    whitelist: MaterialRetrievalWhitelist,
) -> MaterialRetrievalPlan:
    del whitelist
    return MaterialRetrievalPlan(
        scene=visual_brief.scene,
        sub_scene=visual_brief.sub_scene,
        strategy="minimal",
        groups=[],
        source="fallback",
    )


def _allowlisted(value: Any, allowed: set[str]) -> list[str]:
    values = value if isinstance(value, list) else []
    return _dedupe([str(item).strip() for item in values if str(item).strip() in allowed])


def _terms(value: Any) -> list[str]:
    values = value if isinstance(value, list) else []
    return _dedupe([str(item).strip()[:40] for item in values if str(item).strip()])


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result
