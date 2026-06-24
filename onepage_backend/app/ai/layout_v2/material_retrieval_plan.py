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
    categories = set(whitelist.categories)
    sub_categories = set(whitelist.sub_categories)
    styles = set(whitelist.styles)
    raw_groups: list[dict[str, Any]] = []
    scene_key = f"{visual_brief.scene} {visual_brief.sub_scene}".lower()
    if visual_brief.content_length != "long":
        if "food" in scene_key and "食物饮品" in categories:
            raw_groups.append(
                {
                    "role": "focal_sticker",
                    "categories": ["食物饮品"],
                    "sub_categories": _existing(["主食料理", "饮料酒水", "甜品零食"], sub_categories),
                    "query_terms": _fallback_query_terms(visual_brief, ["食物", "料理"]),
                    "styles": _existing(["日系", "可爱"], styles),
                }
            )
        elif any(token in scene_key for token in ("pet", "home")) and "动物生物" in categories:
            raw_groups.append(
                {
                    "role": "focal_sticker",
                    "categories": ["动物生物"],
                    "sub_categories": _existing(["宠物"], sub_categories),
                    "query_terms": _fallback_query_terms(visual_brief, ["宠物", "陪伴"]),
                    "styles": _existing(["可爱", "日系"], styles),
                }
            )
        elif any(token in scene_key for token in ("study", "reading")) and "学习办公" in categories:
            raw_groups.append(
                {
                    "role": "focal_sticker",
                    "categories": ["学习办公"],
                    "sub_categories": _existing(["文具书籍", "考试学习"], sub_categories),
                    "query_terms": _fallback_query_terms(visual_brief, ["学习", "书本", "笔记"]),
                    "styles": _existing(["极简", "日系"], styles),
                }
            )
        elif any(token in scene_key for token in ("outing", "travel")):
            outing_categories = _existing(["人物角色", "交通建筑"], categories)
            if outing_categories:
                raw_groups.append(
                    {
                        "role": "focal_sticker",
                        "categories": outing_categories,
                        "sub_categories": _existing(["人物动作", "交通工具"], sub_categories),
                        "query_terms": _fallback_query_terms(visual_brief, ["出游", "旅行", "户外"]),
                        "styles": _existing(["日系", "可爱"], styles),
                    }
                )
    background_categories = _existing(["通用背景", "场景背景", "自然风景"], categories)
    if background_categories:
        raw_groups.append(
            {
                "role": "background",
                "categories": background_categories[:2],
                "sub_categories": _existing(["通用"], sub_categories),
                "query_terms": _fallback_query_terms(visual_brief, ["低饱和", "纸张", "留白"]),
                "styles": _existing(["日系", "极简"], styles),
            }
        )
    allowed_roles = set(whitelist.roles).intersection(ROLE_DEFAULTS)
    raw_groups = [group for group in raw_groups if group.get("role") in allowed_roles]
    if not raw_groups:
        return MaterialRetrievalPlan(
            scene=visual_brief.scene,
            sub_scene=visual_brief.sub_scene,
            strategy="minimal",
            groups=[],
            source="fallback",
        )
    plan = normalize_material_retrieval_plan(
        {
            "scene": visual_brief.scene,
            "sub_scene": visual_brief.sub_scene,
            "strategy": "minimal" if visual_brief.content_length == "long" else "progressive",
            "groups": raw_groups,
        },
        visual_brief=visual_brief,
        whitelist=whitelist,
    )
    plan.source = "fallback"
    return plan


def _fallback_query_terms(brief: VisualBrief, defaults: list[str]) -> list[str]:
    return _dedupe([*brief.objects, *brief.required_concepts, *brief.visual_keywords, *defaults])[:8]


def _allowlisted(value: Any, allowed: set[str]) -> list[str]:
    values = value if isinstance(value, list) else []
    return _dedupe([str(item).strip() for item in values if str(item).strip() in allowed])


def _terms(value: Any) -> list[str]:
    values = value if isinstance(value, list) else []
    return _dedupe([str(item).strip()[:40] for item in values if str(item).strip()])


def _existing(values: list[str], allowed: set[str]) -> list[str]:
    return [value for value in values if value in allowed]


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
