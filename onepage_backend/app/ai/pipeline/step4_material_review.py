import json
import re
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import structlog

from app.config import settings
from app.ai.gateway.dashscope_vision_client import (
    DashScopeVisionReviewClient,
    build_image_data_url,
    normalize_dashscope_vision_model,
    validate_data_url_size,
)

logger = structlog.get_logger(__name__)

try:
    from PIL import Image, ImageDraw, ImageOps
except Exception:  # pragma: no cover - optional dependency fallback
    Image = None
    ImageDraw = None
    ImageOps = None

RISK_FLAGS = {
    "festival_text",
    "romance",
    "valentine",
    "wedding",
    "party",
    "congratulations",
    "gift",
    "bouquet",
    "religion",
    "crest",
    "dance",
    "ballet",
    "family",
    "off_topic",
    "too_dense",
    "too_loud",
    "text_heavy",
    "unrelated_people",
    "unsafe_background",
    "strong_pattern",
    "unknown_risk",
    "business_sales",
    "expensive",
}

RISK_KEYWORDS = {
    "valentine": ("valentine", "情人节", "バレンタイン", "恋人の日", "love day", "happy valentine"),
    "romance": ("恋爱", "爱情", "情侣", "告白", "约会", "romance", "love", "couple", "heart bouquet"),
    "wedding": ("婚礼", "结婚", "婚纱", "wedding", "bride", "groom", "marriage"),
    "party": ("派对", "party", "庆祝", "celebration", "club", "disco", "生日快乐"),
    "festival_text": ("节日快乐", "happy new year", "merry christmas", "圣诞", "新年", "祝福", "festival", "おめでとう"),
    "congratulations": ("congratulations", "congrats", "おめでとう", "祝福", "恭喜", "生日快乐"),
    "gift": ("gift", "present", "礼物", "プレゼント"),
    "bouquet": ("bouquet", "花束", "捧花"),
    "religion": ("佛", "仏", "菩萨", "宗教", "buddha", "seated buddha"),
    "crest": ("家紋", "family crest", "japanese family crest", "chidori", "千鳥"),
    "dance": ("dance", "dancing", "danceing", "跳舞", "舞蹈", "running", "跑步", "boxer", "拳击"),
    "ballet": ("ballet", "芭蕾"),
    "family": ("family", "家庭", "家人", "人物场景"),
    "too_loud": ("霓虹", "高饱和", "neon", "flashy", "loud"),
    "text_heavy": ("文字", "标语", "slogan", "message", "lettering", "poster"),
    "off_topic": ("佛", "仏", "菩萨", "宗教", "buddha", "家紋", "family crest", "ballet", "芭蕾"),
    "business_sales": ("商务销售", "销售", "促销", "sale", "business", "marketing"),
    "expensive": ("价格昂贵", "昂贵", "高价", "expensive", "diamond hatch", "diamond"),
}

PROTECTED_SCENES = {"self_growth", "study_reflection", "exam_prep", "work"}
SCENE_RISK_FLAGS = {"valentine", "romance", "wedding", "party", "festival_text"}
DAILY_HEALING_HARD_RISK_FLAGS = {
    "valentine",
    "romance",
    "wedding",
    "party",
    "festival_text",
    "congratulations",
    "gift",
    "bouquet",
    "religion",
    "crest",
    "dance",
    "ballet",
    "family",
    "business_sales",
    "expensive",
}
FOOD_HARD_RISK_FLAGS = {
    "valentine",
    "romance",
    "wedding",
    "party",
    "festival_text",
    "congratulations",
    "gift",
    "bouquet",
    "religion",
    "crest",
    "dance",
    "ballet",
    "family",
    "too_loud",
}
FOOD_STRONG_TOKENS = (
    "food",
    "食物",
    "美食",
    "餐饮",
    "餐厅",
    "用餐",
    "铁锅炖",
    "饺子",
    "饺子店",
    "火锅",
    "烧烤",
    "小龙虾",
    "饭",
    "菜",
    "甜品",
    "咖啡",
    "奶茶",
    "餐",
    "吃",
    "好吃",
    "厨房",
    "碗",
    "锅",
)
FOOD_NEUTRAL_TOKENS = (
    "background",
    "背景",
    "纸",
    "纹理",
    "米白",
    "浅棕",
    "暖色",
    "low",
    "低密度",
    "花草",
    "小花",
    "星星",
    "胶带",
    "tape",
    "标签",
    "便签",
    "label",
    "边框",
    "frame",
    "动物",
    "可爱",
    "cute",
)

HEALING_DAILY_TOKENS = (
    "身体不舒服",
    "不舒服",
    "小柴胡",
    "喝药",
    "吃药",
    "药",
    "感冒",
    "发烧",
    "咳嗽",
    "头疼",
    "好一点",
    "恢复",
    "休息",
    "healing",
    "sick",
    "medicine",
    "recover",
)


class _VisionReviewCircuitBreaker:
    def __init__(self) -> None:
        self.failure_count = 0
        self.opened_at = 0.0

    def is_open(self) -> bool:
        if not settings.VISION_REVIEW_CIRCUIT_BREAKER_ENABLED:
            return False
        threshold = max(1, int(settings.VISION_REVIEW_CIRCUIT_BREAKER_THRESHOLD or 3))
        if self.failure_count < threshold:
            return False
        cooldown = max(1, int(settings.VISION_REVIEW_CIRCUIT_BREAKER_COOLDOWN_SECONDS or 300))
        if time.monotonic() - self.opened_at >= cooldown:
            return False
        return True

    def record_failure(self) -> None:
        if not settings.VISION_REVIEW_CIRCUIT_BREAKER_ENABLED:
            return
        self.failure_count += 1
        threshold = max(1, int(settings.VISION_REVIEW_CIRCUIT_BREAKER_THRESHOLD or 3))
        if self.failure_count >= threshold and self.opened_at <= 0:
            self.opened_at = time.monotonic()

    def record_success(self) -> None:
        self.failure_count = 0
        self.opened_at = 0.0


_VISION_CIRCUIT = _VisionReviewCircuitBreaker()


async def run_material_review(ctx: dict) -> dict:
    """Step 4.5: review recalled materials before layout generation."""

    if settings.LAYOUT_ENGINE_VERSION == "v2":
        return _run_material_review_v2(ctx)

    start = time.monotonic()
    task_id = ctx.get("task_id")
    step4 = ctx.get("step4", {})
    step1 = ctx.get("step1", {})
    step3 = ctx.get("step3", {})
    input_json = ctx.get("input_json", {})
    user_text = input_json.get("text", "") or input_json.get("content_text", "")
    groups = step4.get("groups", []) if isinstance(step4, dict) else []

    print(f"STEP4_REVIEW_START task_id={task_id} groups={_group_counts(groups)}", flush=True)

    reviewed_by_type: dict[str, list[dict]] = {"background": [], "decoration": [], "sticker": []}
    rejected: list[dict] = []
    prefiltered: list[dict] = []

    semantic = _force_food_semantic(_semantic_context(step1), user_text)
    for group in groups:
        if not isinstance(group, dict):
            continue
        material_type = str(group.get("material_type") or "").strip()
        for item in group.get("items", []) if isinstance(group.get("items"), list) else []:
            if not isinstance(item, dict):
                continue
            reviewed_item = _review_item_by_rules(
                item,
                material_type=material_type,
                semantic=semantic,
                style_result=step3,
            )
            prefiltered.append(reviewed_item)
            if reviewed_item["decision"] == "reject":
                rejected.append(reviewed_item)
            else:
                target_type = _target_group_type(reviewed_item, material_type)
                reviewed_by_type.setdefault(target_type, []).append(_as_step5_candidate(item, reviewed_item, target_type))

    print(
        "STEP4_REVIEW_PREFILTER "
        f"task_id={task_id} kept={sum(len(v) for v in reviewed_by_type.values())} rejected={len(rejected)}",
        flush=True,
    )

    vision_failed = False
    model_used = "rules"
    vision_reason = _vision_unavailable_reason()
    if not vision_reason and _VISION_CIRCUIT.is_open():
        vision_reason = "circuit_open"
        print(
            f"VISION_REVIEW_CIRCUIT_OPEN task_id={task_id} failure_count={_VISION_CIRCUIT.failure_count}",
            flush=True,
        )
    if not vision_reason:
        try:
            vision_result = await _run_vision_review(
                task_id=task_id,
                user_text=user_text,
                semantic=semantic,
                items=[item for item in prefiltered if item.get("decision") != "reject"],
            )
            if vision_result:
                model_used = normalize_dashscope_vision_model(settings.VISION_REVIEW_MODEL)
                _apply_vision_result(reviewed_by_type, rejected, vision_result, semantic)
                _VISION_CIRCUIT.record_success()
            else:
                print(f"VISION_REVIEW_CLIENT_FALLBACK task_id={task_id} reason=empty_or_unavailable_review", flush=True)
        except Exception as exc:
            vision_failed = True
            _VISION_CIRCUIT.record_failure()
            logger.warning("step4_review_vision_failed", task_id=task_id, error=str(exc))
            print(f"VISION_REVIEW_CLIENT_FALLBACK task_id={task_id} reason={str(exc)[:160]}", flush=True)
    else:
        print(f"VISION_REVIEW_CLIENT_FALLBACK task_id={task_id} reason={vision_reason}", flush=True)

    reviewed_by_type = _limit_reviewed_groups(reviewed_by_type)
    fallback_mode = _fallback_mode_for(semantic, reviewed_by_type)
    if fallback_mode == "neutral_minimal":
        reviewed_by_type = _trim_neutral_minimal(reviewed_by_type)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    reviewed_groups = [
        {"material_type": material_type, "items": items}
        for material_type, items in reviewed_by_type.items()
        if items
    ]
    result = {
        "summary": {
            **(step4.get("summary", {}) if isinstance(step4.get("summary"), dict) else {}),
            "semantic": semantic,
            "review_instructions": _layout_review_instructions(semantic, fallback_mode),
        },
        "groups": reviewed_groups,
        "reviewed_candidates": {
            material_type: [_public_review_item(item) for item in items]
            for material_type, items in reviewed_by_type.items()
        },
        "rejected_materials": [_public_review_item(item) for item in rejected],
        "fallback_mode": fallback_mode,
        "review_summary": {
            "kept_count": sum(1 for item in prefiltered if item.get("decision") == "keep"),
            "downgraded_count": sum(1 for item in prefiltered if item.get("decision") == "downgrade"),
            "rejected_count": len(rejected),
            "model_used": model_used,
            "vision_failed": vision_failed,
            "elapsed_ms": elapsed_ms,
        },
    }

    if settings.PIPELINE_DEBUG_TRACE:
        for item in prefiltered:
            print(
                "STEP4_REVIEW_ITEM "
                f"task_id={task_id} material_id={item.get('material_id')} "
                f"decision={item.get('decision')} flags={item.get('risk_flags')} reason={item.get('reason')}",
                flush=True,
            )
    print(
        "STEP4_REVIEW_RESULT "
        f"task_id={task_id} kept={sum(len(v) for v in reviewed_by_type.values())} "
        f"rejected={len(rejected)} fallback_mode={fallback_mode} model={model_used} vision_failed={vision_failed}",
        flush=True,
    )
    return result


def _run_material_review_v2(ctx: dict) -> dict:
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


def _semantic_context(step1: dict) -> dict:
    text_analysis = step1.get("text_analysis", {}) if isinstance(step1.get("text_analysis"), dict) else {}
    constraints = step1.get("semantic_constraints") or text_analysis.get("semantic_constraints") or {}
    return {
        "topic": step1.get("topic") or text_analysis.get("topic") or "",
        "scene": step1.get("scene") or text_analysis.get("scene") or "daily_life",
        "sub_scene": step1.get("sub_scene") or text_analysis.get("sub_scene") or "general_daily",
        "intent": step1.get("intent") or text_analysis.get("intent") or "daily_record",
        "keywords": step1.get("keywords") or text_analysis.get("keywords") or [],
        "positive_tags": step1.get("positive_tags") or text_analysis.get("positive_tags") or [],
        "avoid_tags": step1.get("avoid_tags") or text_analysis.get("avoid_tags") or [],
        "semantic_constraints": constraints if isinstance(constraints, dict) else {},
    }


def _force_food_semantic(semantic: dict, user_text: str) -> dict:
    text = str(user_text or "").lower()
    if not _contains_any(text, FOOD_STRONG_TOKENS):
        return semantic
    result = dict(semantic)
    result["scene"] = "daily_life"
    result["sub_scene"] = "food_review"
    result["intent"] = "food_record"
    positives = list(result.get("positive_tags") or [])
    avoids = list(result.get("avoid_tags") or [])
    for tag in ["food", "daily", "warm", "happy", "review"]:
        if tag not in positives:
            positives.append(tag)
    for tag in ["romance", "valentine", "wedding", "party", "festival", "congratulations", "bouquet", "gift", "unrelated_people", "religion", "crest", "dance", "ballet"]:
        if tag not in avoids:
            avoids.append(tag)
    result["positive_tags"] = positives
    result["avoid_tags"] = avoids
    constraints = dict(result.get("semantic_constraints") or {})
    constraints.update({"avoid_unrelated_people": True, "avoid_party": True, "avoid_text_heavy_sticker": True})
    result["semantic_constraints"] = constraints
    return result


def _review_item_by_rules(item: dict, *, material_type: str, semantic: dict, style_result: dict) -> dict:
    text = _candidate_text(item)
    risk_flags = _detect_risks(text, item)
    scene = str(semantic.get("scene") or "")
    sub_scene = str(semantic.get("sub_scene") or "")
    intent = str(semantic.get("intent") or "")
    semantic_fit = _semantic_fit(text, semantic)
    style_fit = 0.72 if style_result else 0.65
    visual_safety = 0.82
    background_safety = 0.85
    decision = "keep"
    safe_role = str(item.get("suggested_role") or ("background" if material_type == "background" else material_type))
    reason = "规则通过"

    if material_type == "background":
        if not item.get("background_safe", True):
            risk_flags.add("unsafe_background")
        if str(item.get("density") or "").lower() == "high" or str(item.get("complexity") or "").lower() == "high":
            risk_flags.add("too_dense")
            risk_flags.add("strong_pattern")
        if {"unsafe_background", "too_dense", "strong_pattern"}.intersection(risk_flags):
            decision = "downgrade"
            safe_role = "texture_accent"
            background_safety = 0.35
            visual_safety = 0.58
            reason = "背景纹理较强，降级为小面积氛围素材"

    protected = scene in PROTECTED_SCENES or sub_scene in PROTECTED_SCENES or intent in PROTECTED_SCENES
    if protected and SCENE_RISK_FLAGS.intersection(risk_flags):
        decision = "reject"
        reason = "学习/成长内容规避节日、恋爱、婚礼、派对素材"
        semantic_fit = min(semantic_fit, 0.18)

    if decision != "reject" and _is_healing_daily_context(semantic) and DAILY_HEALING_HARD_RISK_FLAGS.intersection(risk_flags):
        decision = "reject"
        reason = "与日常身体恢复场景语义冲突"
        semantic_fit = min(semantic_fit, 0.18)

    if sub_scene == "food_review":
        food_profile = _food_material_profile(text, item, material_type)
        if FOOD_HARD_RISK_FLAGS.intersection(risk_flags):
            decision = "reject"
            reason = "美食内容规避祝福、花束、礼物、恋爱、婚礼、派对、家纹、宗教、舞蹈等跑题素材"
            semantic_fit = min(semantic_fit, 0.2)
        elif food_profile["large_person"]:
            risk_flags.add("unrelated_people")
            decision = "reject"
            reason = "大人物素材不适合美食记录主视觉"
            semantic_fit = min(semantic_fit, 0.22)
        elif material_type == "sticker" and not food_profile["food_strong"]:
            if food_profile["neutral_allowed"]:
                decision = "downgrade"
                safe_role = "supporting_sticker" if food_profile["animal_cute"] else "small_decoration"
                semantic_fit = min(semantic_fit, 0.58)
                reason = "弱相关中性素材仅作为小装饰，不作为美食主视觉"
            else:
                risk_flags.add("off_topic")
                decision = "reject"
                semantic_fit = min(semantic_fit, 0.18)
                reason = "非食物且非中性素材不适合美食记录"
        elif material_type == "sticker" and food_profile["food_strong"]:
            semantic_fit = max(semantic_fit, 0.72)
        elif material_type == "decoration" and not (food_profile["food_strong"] or food_profile["neutral_allowed"]):
            risk_flags.add("off_topic")
            decision = "reject"
            semantic_fit = min(semantic_fit, 0.2)
            reason = "装饰素材与美食记录关系弱"

    if decision == "downgrade" and safe_role == "focal_sticker":
        safe_role = "supporting_sticker"

    constraints = semantic.get("semantic_constraints") or {}
    if constraints.get("avoid_unrelated_people") and "人物角色" in text and semantic_fit < 0.35:
        risk_flags.add("unrelated_people")
        decision = "reject"
        reason = "人物素材与当前语义关系弱"

    if constraints.get("avoid_text_heavy_sticker") and "text_heavy" in risk_flags:
        decision = "reject"
        reason = "文字类贴纸容易造成语义跑题"

    if semantic_fit < 0.2 and material_type != "background":
        risk_flags.add("off_topic")
        decision = "reject"
        reason = "候选素材与当前内容语义匹配度较低"

    return {
        "material_id": item.get("material_id"),
        "name": item.get("display_name") or item.get("origin_path") or item.get("category") or "",
        "type": material_type,
        "category": item.get("category") or "",
        "original_role": item.get("suggested_role") or material_type,
        "safe_role": safe_role,
        "decision": decision,
        "semantic_fit": round(semantic_fit, 2),
        "style_fit": round(style_fit, 2),
        "visual_safety": round(visual_safety, 2),
        "background_safety": round(background_safety, 2),
        "risk_flags": sorted(flag for flag in risk_flags if flag in RISK_FLAGS),
        "reason": reason,
        "preview_url": item.get("preview_url") or "",
        "file_url": item.get("file_url") or "",
        "food_strong_match": sub_scene == "food_review" and _food_material_profile(text, item, material_type)["food_strong"],
        "neutral_allowed": sub_scene != "food_review" or _food_material_profile(text, item, material_type)["neutral_allowed"],
        "_source": item,
    }


def _candidate_text(item: dict) -> str:
    values: list[str] = []
    for key in (
        "display_name",
        "origin_path",
        "category",
        "material_type",
        "visual_style",
        "complexity",
        "density",
        "importance",
        "raw_file_url",
        "file_url",
        "preview_url",
    ):
        values.append(str(item.get(key) or ""))
    for key in ("tags", "style_tags", "emotion_tags", "scene_tags", "match_reasons"):
        data = item.get(key)
        if isinstance(data, list):
            values.extend(str(value) for value in data)
        elif data:
            values.append(str(data))
    return " ".join(values).lower()


def _detect_risks(text: str, item: dict) -> set[str]:
    flags: set[str] = set()
    for flag, tokens in RISK_KEYWORDS.items():
        if _contains_any(text, tokens):
            flags.add(flag)
    if str(item.get("density") or "").lower() == "high":
        flags.add("too_dense")
    if str(item.get("complexity") or "").lower() == "high":
        flags.add("strong_pattern")
    return flags


def _semantic_fit(text: str, semantic: dict) -> float:
    positives = [str(value).lower() for value in semantic.get("positive_tags", []) if value]
    keywords = [str(value).lower() for value in semantic.get("keywords", []) if value]
    hits = sum(1 for token in [*positives, *keywords] if token and token in text)
    if hits:
        return min(0.94, 0.52 + hits * 0.12)
    if semantic.get("scene") == "daily_life":
        return 0.12
    return 0.32


def _is_healing_daily_context(semantic: dict) -> bool:
    fields = " ".join(
        str(value or "")
        for value in (
            semantic.get("scene"),
            semantic.get("sub_scene"),
            semantic.get("intent"),
            " ".join(str(item) for item in semantic.get("keywords", []) if item),
            " ".join(str(item) for item in semantic.get("positive_tags", []) if item),
            " ".join(str(item) for item in semantic.get("avoid_tags", []) if item),
        )
    ).lower()
    return (
        "health_recovery" in fields
        or "recovery" in fields
        or "healing" in fields
        or "身体" in fields
        or "小柴胡" in fields
        or _contains_any(fields, HEALING_DAILY_TOKENS)
    )


def _food_material_profile(text: str, item: dict, material_type: str) -> dict[str, bool]:
    role = str(item.get("suggested_role") or "").lower()
    category = str(item.get("category") or "")
    density = str(item.get("density") or "").lower()
    importance = str(item.get("importance") or "").lower()
    food_strong = _contains_any(text, FOOD_STRONG_TOKENS)
    neutral_allowed = (
        material_type == "background"
        and (item.get("background_safe", True) is not False)
        and density != "high"
    ) or _contains_any(text, FOOD_NEUTRAL_TOKENS)
    animal_cute = _contains_any(text, ("动物", "可爱", "cute", "熊", "猫", "狗", "鸡"))
    neutral_allowed = neutral_allowed or animal_cute
    large_person = (
        "人物场景" in category
        or "人物场景" in text
        or ("人物角色" in category and not food_strong)
        or ("family" in text and not food_strong)
    )
    non_food_focal = role == "focal_sticker" and not food_strong and not neutral_allowed
    return {
        "food_strong": food_strong,
        "neutral_allowed": neutral_allowed,
        "animal_cute": animal_cute,
        "large_person": large_person or non_food_focal or importance == "focal" and "人物" in text and not food_strong,
    }


def _as_step5_candidate(source: dict, review: dict, material_type: str) -> dict:
    item = dict(source)
    item.update(
        {
            "material_type": material_type,
            "review_decision": review["decision"],
            "safe_role": review["safe_role"],
            "risk_flags": review["risk_flags"],
            "semantic_fit": review["semantic_fit"],
            "style_fit": review["style_fit"],
            "visual_safety": review["visual_safety"],
            "background_safety": review["background_safety"],
            "review_reason": review["reason"],
            "suggested_role": review["safe_role"],
            "food_strong_match": review.get("food_strong_match", False),
            "neutral_allowed": review.get("neutral_allowed", True),
        }
    )
    if material_type == "decoration" and source.get("material_type") == "background":
        item["suggested_zone"] = "edge_accent"
        item["suggested_size"] = "small"
        item["preferred_background"] = False
    return item


def _target_group_type(reviewed_item: dict, original_type: str) -> str:
    if original_type == "background" and reviewed_item.get("decision") == "downgrade":
        return "decoration"
    if original_type in {"background", "decoration", "sticker"}:
        return original_type
    return "decoration"


def _limit_reviewed_groups(groups: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {
        "background": _rank_candidates(groups.get("background", []))[:1],
        "decoration": _unique_by_category(_rank_candidates(groups.get("decoration", [])))[:3],
        "sticker": _limit_stickers(groups.get("sticker", [])),
    }


def _limit_stickers(items: list[dict]) -> list[dict]:
    ranked = _rank_candidates(items)
    result: list[dict] = []
    focal_count = 0
    supporting_count = 0
    seen_categories: set[str] = set()
    for item in ranked:
        role = str(item.get("safe_role") or item.get("suggested_role") or "")
        category = str(item.get("category") or "")
        if role == "focal_sticker":
            if focal_count >= 1:
                continue
            focal_count += 1
        else:
            if supporting_count >= 2:
                continue
            if category and category in seen_categories and supporting_count >= 1:
                continue
            supporting_count += 1
        if category:
            seen_categories.add(category)
        result.append(item)
    return result[:3]


def _unique_by_category(items: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for item in items:
        category = str(item.get("category") or "")
        key = category or str(item.get("material_id") or "")
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _rank_candidates(items: list[dict]) -> list[dict]:
    return sorted(
        [item for item in items if isinstance(item, dict)],
        key=lambda item: (
            float(item.get("semantic_fit") or 0),
            float(item.get("visual_safety") or 0),
            float(item.get("score") or 0),
        ),
        reverse=True,
    )


def _fallback_mode_for(semantic: dict, groups: dict[str, list[dict]]) -> str:
    total = sum(len(items) for items in groups.values())
    if total == 0:
        return "neutral_minimal"
    if semantic.get("sub_scene") != "food_review":
        return "none"
    has_strong_food = any(
        bool(item.get("food_strong_match")) and float(item.get("semantic_fit") or 0) >= 0.65
        for items in groups.values()
        for item in items
    )
    return "none" if has_strong_food else "neutral_minimal"


def _trim_neutral_minimal(groups: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Keep only low-risk lightweight assets when the semantic match is weak."""

    backgrounds = [
        item
        for item in groups.get("background", [])
        if item.get("background_safe", True) is not False
        and str(item.get("density") or "").lower() != "high"
        and not set(item.get("risk_flags") or []).intersection(FOOD_HARD_RISK_FLAGS)
    ][:1]
    stickers = [
        item
        for item in groups.get("sticker", [])
        if item.get("review_decision") == "downgrade"
        and str(item.get("safe_role") or "") in {"supporting_sticker", "small_decoration"}
        and not set(item.get("risk_flags") or []).intersection(FOOD_HARD_RISK_FLAGS)
    ][:1]
    decorations = [
        item
        for item in [*groups.get("decoration", []), *[sticker for sticker in stickers if sticker.get("safe_role") == "small_decoration"]]
        if not set(item.get("risk_flags") or []).intersection(FOOD_HARD_RISK_FLAGS)
    ][:2]
    return {
        "background": backgrounds,
        "decoration": decorations,
        "sticker": [sticker for sticker in stickers if sticker.get("safe_role") != "small_decoration"][:1],
    }


async def _run_vision_review(*, task_id: str, user_text: str, semantic: dict, items: list[dict]) -> dict:
    contact_sheet = _build_contact_sheet(items[: max(1, settings.VISION_REVIEW_MAX_CANDIDATES)])
    if not contact_sheet:
        print(f"STEP4_REVIEW_CONTACT_SHEET task_id={task_id} count=0 mode=unavailable", flush=True)
        return {}

    image_data_uri, sheet_items = contact_sheet
    data_url_bytes = validate_data_url_size(image_data_uri)
    print(
        "VISION_REVIEW_CONTACT_SHEET "
        f"task_id={task_id} mime_type={settings.VISION_REVIEW_CONTACT_SHEET_MIME} "
        f"data_url_bytes={data_url_bytes} items={len(sheet_items)}",
        flush=True,
    )
    prompt = _vision_prompt(user_text=user_text, semantic=semantic, items=sheet_items)
    client = DashScopeVisionReviewClient()
    try:
        print(
            "VISION_REVIEW_CLIENT_START "
            f"task_id={task_id} provider=dashscope model={client.model} candidates={len(sheet_items)}",
            flush=True,
        )
        response = await client.review_contact_sheet(
            prompt=prompt,
            contact_sheet_data_url=image_data_uri,
            task_id=task_id,
        )
        parsed = _parse_json_content(response.get("content"))
        result = _normalize_vision_result(parsed, label_map={str(item["label"]): item for item in sheet_items})
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        print(
            "VISION_REVIEW_CLIENT_OK "
            f"task_id={task_id} reviewed={len(result.get('items', []))} "
            f"input_tokens={usage.get('prompt_tokens') or usage.get('input_tokens') or ''} "
            f"output_tokens={usage.get('completion_tokens') or usage.get('output_tokens') or ''}",
            flush=True,
        )
        return result
    finally:
        await client.close()


def _public_image_urls(items: list[dict]) -> tuple[list[str], list[dict]]:
    urls: list[str] = []
    public_items: list[dict] = []
    for index, item in enumerate(items, start=1):
        source = item.get("_source") if isinstance(item.get("_source"), dict) else item
        url = _public_url(source)
        if not url:
            continue
        urls.append(url)
        public_items.append(
            {
                "index": index,
                "material_id": item.get("material_id"),
                "name": item.get("name"),
                "type": item.get("type"),
                "category": item.get("category"),
            }
        )
    return urls, public_items


def _public_url(item: dict) -> str | None:
    for key in ("preview_url", "file_url", "raw_file_url"):
        url = str(item.get(key) or "").strip()
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return url
    return None


def _vision_unavailable_reason() -> str:
    if not settings.VISION_REVIEW_ENABLED:
        return "disabled"
    if settings.VISION_REVIEW_PROVIDER == "rules":
        return "provider_rules"
    if settings.VISION_REVIEW_PROVIDER != "dashscope":
        return "unsupported_provider"
    if not settings.DASHSCOPE_API_KEY:
        return "missing_api_key"
    return ""


def _vision_enabled() -> bool:
    return _vision_unavailable_reason() == ""


def _build_contact_sheet(items: list[dict]) -> tuple[str, list[dict]] | None:
    if Image is None:
        return None

    thumbs: list[tuple[dict, Image.Image]] = []
    for index, item in enumerate(items, start=1):
        path = _local_preview_path(item.get("_source") or item)
        if not path:
            continue
        try:
            image = Image.open(path).convert("RGBA")
        except Exception:
            continue
        image.thumbnail((220, 180), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (240, 220), (250, 246, 239, 255))
        x = (240 - image.width) // 2
        y = (180 - image.height) // 2 + 24
        canvas.alpha_composite(image, (x, y))
        draw = ImageDraw.Draw(canvas)
        label = f"A{index:02d}"
        draw.rounded_rectangle((8, 8, 58, 34), radius=10, fill=(226, 197, 151, 230))
        draw.text((18, 13), label, fill=(79, 61, 44, 255))
        thumbs.append((item, canvas))

    if not thumbs:
        return None

    columns = 3
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 240, rows * 220), (248, 245, 238))
    for offset, (_, thumb) in enumerate(thumbs):
        x = (offset % columns) * 240
        y = (offset // columns) * 220
        sheet.paste(ImageOps.expand(thumb.convert("RGB"), border=8, fill=(248, 245, 238)), (x, y))

    buffer = BytesIO()
    sheet.save(buffer, format="JPEG", quality=80, optimize=True)
    data_uri = build_image_data_url(buffer.getvalue(), settings.VISION_REVIEW_CONTACT_SHEET_MIME or "image/jpeg")
    sheet_items = [
        {
            "label": f"A{index + 1:02d}",
            "material_id": item.get("material_id"),
            "name": item.get("name"),
            "type": item.get("type"),
            "category": item.get("category"),
        }
        for index, (item, _) in enumerate(thumbs)
    ]
    return data_uri, sheet_items


def _local_preview_path(item: dict) -> Path | None:
    for key in ("origin_path",):
        value = str(item.get(key) or "").strip()
        if value:
            path = Path(value)
            if path.exists() and path.is_file():
                return path
    for key in ("raw_file_url", "preview_url", "file_url"):
        url = str(item.get(key) or "").strip()
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            continue
        if parsed.scheme == "":
            path = Path(url)
            if path.exists() and path.is_file():
                return path
    return None


def _vision_prompt(*, user_text: str, semantic: dict, items: list[dict]) -> str:
    return (
        "你是 AI 手帐 APP 的素材审核模型，不是页面设计师。\n"
        "你的任务是根据用户原始文本、scene/sub_scene/intent、positive_tags、avoid_tags、带编号的候选素材宫格图，"
        "判断每个素材是否适合当前手帐内容。\n"
        "必须遵守：语义明显跑题的素材必须 reject；中性但弱相关的素材可以 downgrade；"
        "宁可少用素材，也不能强行乱配；没有强相关素材时，优先保留中性、低密度、简约素材；"
        "检查素材中的可见文字，尤其是情人节、婚礼、恋爱、派对、祝福、礼物等强语义；"
        "检查无关人物大贴纸；检查背景是否高密度、强图案、影响文字阅读；高密度背景不得作为 full_bleed。\n"
        "只输出 JSON；不要输出 Markdown；不要输出解释性前后缀。\n"
        f"用户内容：{user_text}\n"
        f"语义结果：{json.dumps(semantic, ensure_ascii=False)}\n"
        f"素材编号：{json.dumps(items, ensure_ascii=False)}\n"
        "输出格式："
        "{\"items\":[{\"label\":\"A01\",\"detected_type\":\"background|sticker|decoration|unknown\","
        "\"detected_objects\":[],\"detected_text\":\"\",\"semantic_fit\":0.0,\"style_fit\":0.0,"
        "\"visual_safety\":0.0,\"background_safety\":0.0,\"risk_flags\":[],"
        "\"decision\":\"keep|downgrade|reject\","
        "\"safe_role\":\"background|focal_sticker|supporting_sticker|small_decoration|none\","
        "\"reason\":\"\"}],"
        "\"summary\":{\"kept_count\":0,\"downgraded_count\":0,\"rejected_count\":0,\"fallback_needed\":false}}"
    )


def _parse_json_content(content: str | None) -> dict:
    if not content:
        return {}
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    if "{" in text and "}" in text:
        text = text[text.find("{") : text.rfind("}") + 1]
    try:
        data = json.loads(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_vision_result(data: dict, *, label_map: dict[str, dict]) -> dict:
    raw_items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(raw_items, list):
        return {}
    decisions = {"keep", "downgrade", "reject"}
    safe_roles = {"background", "focal_sticker", "supporting_sticker", "small_decoration", "none"}
    normalized: list[dict] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        label = str(raw_item.get("label") or "").strip()
        sheet_item = label_map.get(label)
        if sheet_item is None:
            logger.warning("step4_review_unknown_label_ignored", label=label)
            continue
        decision = str(raw_item.get("decision") or "").strip()
        if decision not in decisions:
            decision = "downgrade"
        safe_role = str(raw_item.get("safe_role") or "").strip()
        if safe_role not in safe_roles:
            safe_role = "none" if decision == "reject" else "small_decoration"
        normalized.append(
            {
                "label": label,
                "material_id": sheet_item.get("material_id"),
                "detected_type": str(raw_item.get("detected_type") or "unknown"),
                "detected_objects": raw_item.get("detected_objects") if isinstance(raw_item.get("detected_objects"), list) else [],
                "detected_text": str(raw_item.get("detected_text") or ""),
                "semantic_fit": _bounded_float(raw_item.get("semantic_fit"), 0.5),
                "style_fit": _bounded_float(raw_item.get("style_fit"), 0.5),
                "visual_safety": _bounded_float(raw_item.get("visual_safety"), 0.7),
                "background_safety": _bounded_float(raw_item.get("background_safety"), 0.7),
                "risk_flags": [str(flag) for flag in raw_item.get("risk_flags", []) if str(flag) in RISK_FLAGS]
                if isinstance(raw_item.get("risk_flags"), list)
                else [],
                "decision": decision,
                "safe_role": safe_role,
                "reason": str(raw_item.get("reason") or ""),
            }
        )
    return {"items": normalized, "summary": data.get("summary") if isinstance(data.get("summary"), dict) else {}}


def _apply_vision_result(groups: dict[str, list[dict]], rejected: list[dict], vision_result: dict, semantic: dict) -> None:
    items = vision_result.get("items")
    if not isinstance(items, list):
        return
    by_id: dict[str, dict] = {}
    for material_type, group_items in groups.items():
        for item in group_items:
            material_id = str(item.get("material_id") or "")
            if material_id:
                by_id[material_id] = item
    for model_item in items:
        if not isinstance(model_item, dict):
            continue
        material_id = str(model_item.get("material_id") or "")
        item = by_id.get(material_id)
        if not item:
            continue
        model_flags = {str(flag) for flag in model_item.get("risk_flags", []) if str(flag) in RISK_FLAGS}
        item["risk_flags"] = sorted(set(item.get("risk_flags", [])) | model_flags)
        item["semantic_fit"] = _bounded_float(model_item.get("semantic_fit"), item.get("semantic_fit", 0.5))
        item["style_fit"] = _bounded_float(model_item.get("style_fit"), item.get("style_fit", 0.5))
        item["visual_safety"] = _bounded_float(model_item.get("visual_safety"), item.get("visual_safety", 0.7))
        item["background_safety"] = _bounded_float(model_item.get("background_safety"), item.get("background_safety", 0.7))
        item["review_reason"] = str(model_item.get("reason") or item.get("review_reason") or "")
        decision = str(model_item.get("decision") or "")
        if decision == "reject":
            item["review_decision"] = "reject"
            rejected.append(item)
            _remove_group_item(groups, material_id)
        elif decision == "downgrade":
            item["review_decision"] = "downgrade"
            safe_role = str(model_item.get("safe_role") or "")
            if safe_role in {"background", "focal_sticker"}:
                safe_role = "supporting_sticker"
            item["safe_role"] = safe_role if safe_role in {"supporting_sticker", "small_decoration", "texture_accent"} else "small_decoration"
            item["suggested_role"] = item["safe_role"]
        elif decision == "keep":
            safe_role = str(model_item.get("safe_role") or "")
            if safe_role in {"background", "focal_sticker", "supporting_sticker", "small_decoration"}:
                item["safe_role"] = safe_role
                item["suggested_role"] = safe_role


def _remove_group_item(groups: dict[str, list[dict]], material_id: str) -> None:
    for material_type, group_items in groups.items():
        groups[material_type] = [item for item in group_items if str(item.get("material_id") or "") != material_id]


def _bounded_float(value, fallback: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return float(fallback)


def _layout_review_instructions(semantic: dict, fallback_mode: str) -> list[str]:
    instructions = [
        "只使用 reviewed_candidates.groups 中的素材，不要使用原始 Step4 候选。",
        "拒绝或高风险素材不得出现在最终 Layout JSON 中。",
        "downgrade 素材只能作为小面积装饰，不得作为全屏背景或主视觉。",
    ]
    if semantic.get("scene") == "self_growth" or semantic.get("sub_scene") == "study_reflection":
        instructions.append("学习/成长/备考内容禁止使用情人节、恋爱、婚礼、派对、节日祝福素材。")
    if semantic.get("sub_scene") == "food_review":
        instructions.append("美食记录禁止使用 party/family/ballet/dance/Japanese family crest/chidori/buddha/boxer/valentine/wedding/romance/congratulations/gift/bouquet/祝福/花束/礼物/人物场景等跑题素材。")
    if fallback_mode == "neutral_minimal":
        instructions.append("没有安全强相关素材时，使用纯色或低密度纸感背景，只保留必要文字、日期和心情标签；不要强行添加 focal_sticker，最多 1 个 supporting_sticker 和 2 个 decoration。")
    return instructions


def _public_review_item(item: dict) -> dict:
    if "_source" in item:
        source = item.get("_source") if isinstance(item.get("_source"), dict) else {}
        return {
            key: item.get(key)
            for key in (
                "material_id",
                "name",
                "type",
                "category",
                "original_role",
                "safe_role",
                "decision",
                "semantic_fit",
                "style_fit",
                "visual_safety",
                "background_safety",
                "risk_flags",
                "reason",
                "preview_url",
                "file_url",
            )
        } | {
            "preview_url": item.get("preview_url") or source.get("preview_url"),
            "file_url": item.get("file_url") or source.get("file_url"),
        }
    return {
        "material_id": item.get("material_id"),
        "name": item.get("display_name") or item.get("name") or item.get("origin_path"),
        "type": item.get("material_type") or item.get("type"),
        "category": item.get("category"),
        "original_role": item.get("original_role") or item.get("suggested_role"),
        "safe_role": item.get("safe_role"),
        "decision": item.get("review_decision") or item.get("decision"),
        "semantic_fit": item.get("semantic_fit"),
        "style_fit": item.get("style_fit"),
        "visual_safety": item.get("visual_safety"),
        "background_safety": item.get("background_safety"),
        "risk_flags": item.get("risk_flags") or [],
        "reason": item.get("review_reason") or item.get("reason"),
        "preview_url": item.get("preview_url"),
        "file_url": item.get("file_url"),
    }


def _group_counts(groups: list[dict]) -> dict[str, int]:
    result: dict[str, int] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        material_type = str(group.get("material_type") or "unknown")
        result[material_type] = len(group.get("items", []) if isinstance(group.get("items"), list) else [])
    return result


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(str(token).lower() in lowered for token in tokens)
