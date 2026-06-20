from __future__ import annotations

import math
import re
from typing import Any

from app.ai.layout_v2.enums import MATERIAL_ROLES, MaterialRole
from app.ai.layout_v2.schemas import MaterialCandidate, MaterialVisualMetadata, VisualBBox, VisualBrief


RISK_TEXT = {
    "valentine": ("valentine", "情人节", "バレンタイン"),
    "wedding": ("wedding", "婚礼", "结婚", "婚纱", "bride", "groom"),
    "romance": ("romance", "恋爱", "情侣", "告白", "约会"),
    "festival_text": ("congratulations", "congrats", "祝福", "恭喜", "おめでとう", "happy new year", "merry christmas"),
    "medical": ("medical", "医院", "医生", "护士", "病院"),
    "sick": ("sick", "病人", "生病", "发烧"),
    "wheelchair": ("wheelchair", "轮椅"),
    "elderly_care": ("elderly care", "老人护理", "介护"),
    "religion": ("buddha", "佛", "菩萨", "宗教"),
    "business_sales": ("business", "sale", "促销", "销售"),
    "party": ("party", "派对", "celebration", "庆祝"),
}

ROLE_THRESHOLDS = {
    MaterialRole.BACKGROUND: 0.42,
    MaterialRole.FOCAL_STICKER: 0.55,
    MaterialRole.SUPPORTING_STICKER: 0.48,
    MaterialRole.TAPE: 0.28,
    MaterialRole.FRAME: 0.28,
    MaterialRole.DECORATION: 0.28,
}


async def retrieve_material_role_groups(
    *,
    brief: VisualBrief,
    required_roles: set[str],
    user_id: str | None,
    limit_per_role: int = 5,
) -> dict[str, Any]:
    from app.core.database import async_session_factory
    from app.services.material_service import MaterialService

    role_groups: dict[str, list[dict[str, Any]]] = {role: [] for role in required_roles if role in MATERIAL_ROLES}
    rejected: list[dict[str, Any]] = []
    async with async_session_factory() as db:
        service = MaterialService(db)
        materials = await service.load_visible_layout_materials(user_id=user_id)
        for material in materials:
            candidate_base, reason = _candidate_from_material(material, service=service, user_id=user_id)
            if candidate_base is None:
                rejected.append({"material_id": str(material.id), "reason": reason})
                continue
            role = candidate_base["role"]
            if role not in role_groups:
                continue
            candidate, reason = score_candidate(candidate_base, brief=brief, role=MaterialRole(role))
            if candidate is None:
                rejected.append({"material_id": str(material.id), "role": role, "reason": reason})
                continue
            role_groups[role].append(candidate.model_dump(mode="json"))

    for role, items in role_groups.items():
        items.sort(key=lambda item: (float(item["total_score"]), _preference_score(item)), reverse=True)
        role_groups[role] = items[:limit_per_role]
    return {"role_groups": role_groups, "rejected": rejected}


def score_candidate(
    candidate_data: dict[str, Any],
    *,
    brief: VisualBrief,
    role: MaterialRole,
) -> tuple[MaterialCandidate | None, str]:
    metadata = MaterialVisualMetadata.model_validate(candidate_data["metadata"])
    conflicts = set(metadata.risk_flags).intersection(brief.excluded_concepts)
    if conflicts:
        return None, f"excluded_concept:{','.join(sorted(conflicts))}"
    if metadata.text_heavy and not _content_explicitly_requests_text(brief, metadata.detected_text):
        return None, "text_heavy_without_matching_request"
    if role is MaterialRole.BACKGROUND and (
        not metadata.background_safe or metadata.density == "high" or metadata.complexity == "high"
    ):
        return None, "unsafe_background"

    subject_score, subject_hits = _match_score(
        [brief.primary_subject, *brief.objects, *brief.required_concepts],
        [*metadata.subjects, *metadata.objects],
    )
    action_score, action_hits = _match_score([brief.primary_action, *brief.required_concepts], metadata.actions)
    scene_score, scene_hits = _match_score(
        [brief.scene, brief.sub_scene, *brief.environment, *brief.required_concepts],
        [*metadata.scenes, *metadata.objects, *metadata.subjects],
    )
    role_score = 1.0 if metadata.suggested_role is role else 0.0
    style_score, style_hits = _match_score(
        brief.preferred_color_tone,
        [metadata.visual_style, metadata.color_tone],
    )

    if role in {MaterialRole.FOCAL_STICKER, MaterialRole.SUPPORTING_STICKER} and not (
        subject_hits or action_hits or _required_concept_hit(brief, metadata)
    ):
        return None, "missing_subject_action_or_required_concept"
    if role is MaterialRole.BACKGROUND and not scene_hits:
        return None, "missing_environment_or_scene_match"

    if role in {MaterialRole.TAPE, MaterialRole.FRAME, MaterialRole.DECORATION}:
        semantic_score = 0.45 * role_score + 0.35 * style_score + 0.20 * _low_density_score(metadata)
    else:
        semantic_score = (
            0.35 * subject_score
            + 0.20 * action_score
            + 0.20 * scene_score
            + 0.15 * role_score
            + 0.10 * style_score
        )
    if semantic_score < ROLE_THRESHOLDS[role]:
        return None, f"score_below_threshold:{semantic_score:.3f}"

    reasons = [
        *(f"subject:{item}" for item in subject_hits),
        *(f"action:{item}" for item in action_hits),
        *(f"scene:{item}" for item in scene_hits),
        *(f"style:{item}" for item in style_hits),
        f"role:{role.value}",
    ]
    candidate = MaterialCandidate.model_validate(
        {
            **candidate_data,
            "role": role,
            "semantic_score": round(semantic_score, 4),
            "style_score": round(style_score, 4),
            "total_score": round(semantic_score, 4),
            "match_reasons": reasons,
        }
    )
    return candidate, ""


def normalize_material_metadata(material: Any) -> MaterialVisualMetadata:
    meta = dict(getattr(material, "meta_info", None) or {})
    role = _material_role(material, meta)
    risk_flags = _dedupe([*list(meta.get("risk_flags") or []), *_risk_flags_from_text(_material_text(material, meta))])
    bbox_value = meta.get("visual_bbox") if isinstance(meta.get("visual_bbox"), dict) else {}
    try:
        bbox = VisualBBox.model_validate(bbox_value or {})
    except Exception:
        bbox = VisualBBox()
    return MaterialVisualMetadata.model_validate(
        {
            "subjects": _as_list(meta.get("subjects") or meta.get("subject")),
            "actions": _as_list(meta.get("actions") or meta.get("action")),
            "scenes": _as_list(meta.get("scenes") or meta.get("scene") or getattr(material, "scene_tags", None)),
            "objects": _as_list(meta.get("objects") or meta.get("keywords") or meta.get("semantic_tags")),
            "detected_text": str(meta.get("detected_text") or ""),
            "text_heavy": _as_bool(meta.get("text_heavy"), False),
            "risk_flags": risk_flags,
            "suggested_role": role,
            "background_safe": _as_bool(meta.get("background_safe"), role is MaterialRole.BACKGROUND),
            "visual_style": str(meta.get("visual_style") or _first(getattr(material, "style_tags", None)) or ""),
            "color_tone": str(meta.get("color_tone") or ""),
            "complexity": _density(meta.get("complexity")),
            "density": _density(meta.get("density")),
            "visual_bbox": bbox.model_dump(),
            "manual_override": _as_bool(meta.get("manual_override"), False),
            "annotation_version": str(meta.get("annotation_version") or "v1_compat"),
        }
    )


def _candidate_from_material(material: Any, *, service: Any, user_id: str | None) -> tuple[dict[str, Any] | None, str]:
    metadata = normalize_material_metadata(material)
    meta = dict(material.meta_info or {})
    if metadata.suggested_role is MaterialRole.NONE:
        return None, "missing_valid_role"
    if _as_bool(meta.get("semantic_blocked"), False):
        return None, "semantic_blocked"
    file_url = str(service.build_material_proxy_url(material, "asset", user_id) or "").strip()
    if not file_url:
        return None, "missing_url"
    width = _positive_number(meta.get("asset_width"))
    height = _positive_number(meta.get("asset_height"))
    if meta.get("asset_width") is not None and width is None:
        return None, "invalid_asset_width"
    if meta.get("asset_height") is not None and height is None:
        return None, "invalid_asset_height"
    state = getattr(material, "_user_state", None)
    return {
        "material_id": str(material.id),
        "role": metadata.suggested_role.value,
        "file_url": file_url,
        "preview_url": str(service.build_material_proxy_url(material, "preview", user_id) or ""),
        "raw_file_url": str(meta.get("raw_file_url") or material.file_url or ""),
        "mime_type": str(meta.get("mime_type") or ""),
        "metadata": metadata.model_dump(mode="json"),
        "category": str(meta.get("category") or ""),
        "display_name": str(meta.get("display_name") or meta.get("filename") or ""),
        "asset_width": width,
        "asset_height": height,
        "is_favorite": bool(getattr(state, "is_favorite", False)),
        "is_recent": bool(getattr(state, "last_used_at", None)),
    }, ""


def _material_role(material: Any, meta: dict[str, Any]) -> MaterialRole:
    value = str(meta.get("suggested_role") or "").strip()
    try:
        return MaterialRole(value)
    except ValueError:
        if meta.get("manual_override") is True:
            return MaterialRole.NONE
    material_type = str(getattr(material, "material_type", "") or "")
    text = _material_text(material, meta)
    if material_type == "background":
        return MaterialRole.BACKGROUND
    if material_type == "decoration":
        if any(token in text for token in ("胶带", "tape", "丝带")):
            return MaterialRole.TAPE
        if any(token in text for token in ("边框", "frame", "框架")):
            return MaterialRole.FRAME
        return MaterialRole.DECORATION
    if material_type == "sticker":
        usage_type = str(meta.get("usage_type") or "").strip().lower()
        if usage_type in {"主体", "主体贴图", "主贴纸", "focal", "focal_sticker"}:
            return MaterialRole.FOCAL_STICKER
        return MaterialRole.SUPPORTING_STICKER
    return MaterialRole.NONE


def _required_concept_hit(brief: VisualBrief, metadata: MaterialVisualMetadata) -> bool:
    _, hits = _match_score(
        brief.required_concepts,
        [*metadata.subjects, *metadata.actions, *metadata.scenes, *metadata.objects],
    )
    return bool(hits)


def _match_score(expected: list[str], actual: list[str]) -> tuple[float, list[str]]:
    expected_tokens = _tokenize(expected)
    actual_tokens = _tokenize(actual)
    hits = sorted(
        {
            expected_token
            for expected_token in expected_tokens
            if any(_tokens_match(expected_token, actual_token) for actual_token in actual_tokens)
        }
    )
    return (min(1.0, len(hits) / max(1, min(3, len(expected_tokens)))), hits)


def _tokens_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return left == right or (len(left) >= 2 and left in right) or (len(right) >= 2 and right in left)


def _tokenize(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip().lower()
        if not text:
            continue
        parts = re.findall(r"[\u4e00-\u9fff]{1,}|[a-z0-9_]+", text)
        result.extend(parts or [text])
    return _dedupe(result)


def _risk_flags_from_text(text: str) -> list[str]:
    lowered = text.lower()
    return [flag for flag, tokens in RISK_TEXT.items() if any(token.lower() in lowered for token in tokens)]


def _material_text(material: Any, meta: dict[str, Any]) -> str:
    values = [
        str(meta.get("display_name") or ""),
        str(meta.get("filename") or ""),
        str(meta.get("category") or ""),
        str(meta.get("sub_category") or ""),
        str(meta.get("usage_type") or ""),
        str(meta.get("detected_text") or ""),
        *[str(item) for item in _as_list(meta.get("semantic_tags"))],
    ]
    return " ".join(values).lower()


def _content_explicitly_requests_text(brief: VisualBrief, detected_text: str) -> bool:
    if not detected_text.strip():
        return False
    concepts = " ".join([brief.topic, *brief.visual_keywords, *brief.required_concepts]).lower()
    return any(token in concepts for token in ("quote", "文字", "标语", "祝福"))


def _low_density_score(metadata: MaterialVisualMetadata) -> float:
    return 1.0 if metadata.density == "low" else 0.55 if metadata.density == "medium" else 0.0


def _preference_score(item: dict[str, Any]) -> float:
    return (0.02 if item.get("is_favorite") else 0.0) + (0.01 if item.get("is_recent") else 0.0)


def _positive_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _density(value: Any) -> str:
    text = str(value or "medium").strip().lower()
    return text if text in {"low", "medium", "high"} else "medium"


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return default


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item).strip()]


def _first(value: Any) -> str:
    values = _as_list(value)
    return values[0] if values else ""


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
