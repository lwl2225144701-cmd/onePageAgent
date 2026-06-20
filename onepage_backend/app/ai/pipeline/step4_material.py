import json
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


async def run_material_matching(ctx: dict) -> dict:
    """Step 4: Match materials based on style, emotion, scene, and weather."""
    if settings.LAYOUT_ENGINE_VERSION == "v2":
        return await _run_material_matching_v2(ctx)
    step1 = ctx.get("step1", {})
    step2 = ctx.get("step2", {})
    step3 = ctx.get("step3", {})
    input_json = ctx["input_json"]
    user_id = ctx.get("user_id")

    emotion = normalize_emotion(step2.get("primary_emotion", "") or input_json.get("mood", ""))
    style = step3.get("theme", "")
    content_text = input_json.get("text", "") or input_json.get("content_text", "")
    sub_scene = step1_sub_scene(step1)
    journal_context = ctx.get("journal_context", {}) if isinstance(ctx.get("journal_context"), dict) else {}
    weather_context = journal_weather_context(journal_context)
    scene = infer_scene(
        text=content_text,
        step1_scene_value=step1_scene(ctx.get("step1", {})),
        step1_sub_scene_value=sub_scene,
        weather=weather_context["weather"] or "",
    )
    if is_food_text(content_text) or sub_scene == "food_review":
        scene = "daily_life"
        sub_scene = "food_review"
    weather = weather_context["weather"] or ""
    keywords = []

    from app.services.material_service import MaterialService

    keywords = MaterialService.extract_candidate_keywords(
        content_text,
        json_text(step1.get("text_analysis", {})),
        " ".join(step2.get("keywords", []) or []),
        input_json.get("mood", ""),
        scene,
        sub_scene,
        weather,
    )
    keywords = dedupe_keywords(
        [
            *keywords,
            *journal_context.get("semantic_tags", []),
            *journal_context.get("recommended_material_tags", []),
        ]
    )
    print(
        "STEP4_WEATHER_CONTEXT "
        f"task_id={ctx.get('task_id')} "
        f"weather={weather or 'unknown'} "
        f"weather_icon={weather_context['weather_icon'] or ''} "
        f"location={weather_context['location'] or ''} "
        f"source={journal_context.get('source') or 'request_environment'} "
        f"context_success={str(weather_context['tool_success']).lower()}",
        flush=True,
    )

    for attempt in range(1, 3):
        try:
            candidates = await retrieve_candidates(
                user_id=user_id,
                emotion=emotion,
                scene=scene,
                style=style,
                weather=weather,
                keywords=keywords,
            )
            summary = candidates.get("summary", {}) if isinstance(candidates.get("summary"), dict) else {}
            summary["sub_scene"] = sub_scene
            candidates["summary"] = summary
            annotate_layout_suggestions(candidates, emotion=emotion, scene=scene, style=style)
            recall_summary = summarize_recall_candidates(candidates)
            logger.info(
                "step4_material_candidates",
                user_id=user_id,
                input_text=(input_json.get("text", "") or input_json.get("content_text", ""))[:180],
                emotion=emotion,
                scene=scene,
                sub_scene=sub_scene,
                style=style,
                weather=weather,
                keywords=keywords,
                total_candidates=recall_summary["total_candidates"],
                group_counts=recall_summary["group_counts"],
            )
            print(
                f"STEP4_RECALL task_id={ctx.get('task_id')} scene={scene} sub_scene={sub_scene} total={recall_summary['total_candidates']} groups={recall_summary['group_counts']}",
                flush=True,
            )
            print(
                "ONEPAGE_CONTEXT_EXTRACTED "
                f"task_id={ctx.get('task_id')} scene={scene} sub_scene={sub_scene} "
                f"emotion={emotion} weather={weather or 'unknown'} keywords={json.dumps(keywords, ensure_ascii=False)}",
                flush=True,
            )
            print(
                "ONEPAGE_WEATHER_RESOLVED "
                f"task_id={ctx.get('task_id')} weather={weather or 'unknown'} "
                f"location={weather_context['location'] or ''} success={str(weather_context['tool_success']).lower()}",
                flush=True,
            )
            print(
                "ONEPAGE_MATERIAL_CANDIDATES "
                f"task_id={ctx.get('task_id')} total={recall_summary['total_candidates']} "
                f"groups={json.dumps(recall_summary['group_counts'], ensure_ascii=False)} "
                f"roles={json.dumps(summary.get('role_counts', {}), ensure_ascii=False)}",
                flush=True,
            )
            if settings.LOG_FULL_CANDIDATES:
                print(
                    f"STEP4_CANDIDATE_NAMES task_id={ctx.get('task_id')} items={json.dumps(summarize_candidate_names(candidates), ensure_ascii=False)}",
                    flush=True,
                )
            return candidates
        except Exception as exc:
            logger.warning("step4_material_failed", attempt=attempt, error=str(exc))
            print(f"STEP4_FAILED task_id={ctx.get('task_id')} attempt={attempt} error={str(exc)[:240]}", flush=True)
            await dispose_db_engine()

    return {"summary": {"emotion": emotion, "scene": scene, "sub_scene": sub_scene, "style": style, "weather": weather, "keywords": keywords}, "groups": []}


async def _run_material_matching_v2(ctx: dict) -> dict:
    from app.ai.layout_v2.catalog import public_template_summary
    from app.ai.layout_v2.material_retriever import retrieve_material_role_groups
    from app.ai.layout_v2.schemas import VisualBrief
    from app.ai.layout_v2.template_filter import filter_templates, required_roles_for_templates
    from app.ai.layout_v2.visual_brief import build_visual_brief_from_context

    brief = VisualBrief.model_validate(ctx.get("visual_brief") or build_visual_brief_from_context(ctx))
    templates = filter_templates(brief)
    required_roles = required_roles_for_templates(templates)
    retrieved = await retrieve_material_role_groups(
        brief=brief,
        required_roles=required_roles,
        user_id=ctx.get("user_id"),
    )
    role_groups = retrieved["role_groups"]
    template_summaries = [public_template_summary(template) for template in templates]
    print(
        "ONEPAGE_TEMPLATE_CANDIDATES "
        f"task_id={ctx.get('task_id')} items={json.dumps([item['id'] for item in template_summaries], ensure_ascii=False)}",
        flush=True,
    )
    print(
        "ONEPAGE_MATERIAL_ROLE_CANDIDATES "
        f"task_id={ctx.get('task_id')} counts={json.dumps({role: len(items) for role, items in role_groups.items()}, ensure_ascii=False)}",
        flush=True,
    )
    if retrieved["rejected"]:
        print(
            "ONEPAGE_MATERIAL_REJECTED "
            f"task_id={ctx.get('task_id')} items={json.dumps(retrieved['rejected'][:40], ensure_ascii=False)}",
            flush=True,
        )
    return {
        "summary": {
            "layout_engine": "v2",
            "visual_brief": brief.model_dump(mode="json"),
            "template_candidates": template_summaries,
            "required_roles": sorted(required_roles),
        },
        "role_groups": role_groups,
        "rejected_materials": retrieved["rejected"],
    }


async def retrieve_candidates(
    *,
    user_id: str | None,
    emotion: str,
    scene: str,
    style: str,
    weather: str,
    keywords: list[str],
) -> dict:
    from app.core.database import async_session_factory
    from app.services.material_service import MaterialService

    db = async_session_factory()
    try:
        svc = MaterialService(db)
        return await svc.retrieve_layout_candidates(
            user_id=user_id,
            emotion=emotion,
            scene=scene,
            style=style,
            weather=weather,
            keywords=keywords,
        )
    finally:
        try:
            await db.close()
        except Exception as exc:
            logger.warning("step4_db_session_close_failed", error=str(exc))


async def dispose_db_engine() -> None:
    try:
        from app.core.database import engine

        await engine.dispose()
    except Exception as exc:
        logger.warning("step4_db_engine_dispose_failed", error=str(exc))


def step1_scene(step1: dict) -> str:
    text_analysis = step1.get("text_analysis", {})
    if isinstance(text_analysis, dict):
        return text_analysis.get("scene", "") or ""
    return ""


def normalize_emotion(value: str) -> str:
    text = str(value or "").strip().lower()
    mapping = {
        "happy": "开心",
        "excited": "开心",
        "calm": "平静",
        "neutral": "平静",
        "healing": "治愈",
        "sad": "难过",
        "nostalgic": "怀旧",
        "开心": "开心",
        "高兴": "开心",
        "快乐": "开心",
        "平静": "平静",
        "治愈": "治愈",
        "难过": "难过",
        "伤心": "难过",
        "怀旧": "怀旧",
    }
    return mapping.get(text, str(value or "").strip())


def infer_scene(*, text: str, step1_scene_value: str, step1_sub_scene_value: str = "", weather: str) -> str:
    if step1_sub_scene_value == "food_review" or is_food_text(text):
        return "daily_life"
    if step1_scene_value:
        return step1_scene_value

    haystack = f"{text} {weather}".lower()
    scene_keywords = [
        ("海边", ("海", "海边", "沙滩", "浪花", "晚霞", "beach", "sea", "ocean")),
        ("雨天", ("雨", "下雨", "阴天", "雨伞", "rain")),
        ("咖啡", ("咖啡", "拿铁", "咖啡厅", "coffee")),
        ("阅读", ("书", "阅读", "读书", "书店", "read", "book")),
        ("工作", ("工作", "办公室", "加班", "typing", "office")),
        ("旅行", ("旅行", "出发", "露营", "远方", "travel", "trip")),
        ("家庭", ("家", "做饭", "家人", "family", "home")),
    ]
    for scene, tokens in scene_keywords:
        if any(token in haystack for token in tokens):
            return scene
    return ""


FOOD_SCENE_TOKENS = (
    "铁锅炖",
    "饺子",
    "饺子店",
    "好吃",
    "美食",
    "吃了",
    "餐厅",
    "用餐",
    "餐饮",
    "点赞",
    "好评",
    "咖啡",
    "奶茶",
    "火锅",
    "烧烤",
    "小龙虾",
    "饭",
    "菜",
    "甜品",
)


def is_food_text(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(token.lower() in lowered for token in FOOD_SCENE_TOKENS)


def step1_sub_scene(step1: dict) -> str:
    if isinstance(step1, dict):
        value = str(step1.get("sub_scene") or "").strip()
        if value:
            return value
        text_analysis = step1.get("text_analysis", {})
        if isinstance(text_analysis, dict):
            return str(text_analysis.get("sub_scene") or "").strip()
    return ""


def json_text(value: dict) -> str:
    if not isinstance(value, dict):
        return ""
    parts: list[str] = []
    for field in ("summary", "scene", "objects", "time"):
        data = value.get(field)
        if isinstance(data, list):
            parts.extend(str(item) for item in data)
        elif data:
            parts.append(str(data))
    return " ".join(parts)


def journal_weather_context(journal_context: dict) -> dict:
    weather_data = journal_context.get("weather", {}) if isinstance(journal_context.get("weather"), dict) else {}
    location_data = journal_context.get("location", {}) if isinstance(journal_context.get("location"), dict) else {}
    weather_success = bool(journal_context.get("weather_success") and weather_data.get("text"))
    return {
        "weather": str(weather_data.get("text") or "").strip() if weather_success else "",
        "weather_icon": str(weather_data.get("icon") or "").strip() if weather_success else "",
        "location": str(location_data.get("city") or location_data.get("input_location") or "").strip(),
        "tool_success": bool(journal_context.get("tool_success", journal_context.get("ok"))),
    }


def dedupe_keywords(values: list) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def summarize_recall_candidates(candidates: dict) -> dict:
    groups = candidates.get("groups", []) if isinstance(candidates, dict) else []
    group_counts: dict[str, int] = {}
    recalled_materials: dict[str, list[dict]] = {}
    total_candidates = 0

    for group in groups:
        material_type = str(group.get("material_type", "")).strip() or "unknown"
        items = group.get("items", []) if isinstance(group, dict) else []
        group_counts[material_type] = len(items)
        total_candidates += len(items)
        recalled_materials[material_type] = [
            {
                "material_id": item.get("material_id"),
                "display_name": item.get("display_name") or item.get("origin_path"),
                "origin_path": item.get("origin_path"),
                "category": item.get("category"),
                "aspect_ratio": item.get("aspect_ratio"),
                "score": item.get("score"),
                "match_reasons": item.get("match_reasons", []),
            }
            for item in items
        ]

    return {
        "total_candidates": total_candidates,
        "group_counts": group_counts,
        "recalled_materials": recalled_materials,
    }


def summarize_candidate_links(candidates: dict) -> dict[str, list[dict]]:
    groups = candidates.get("groups", []) if isinstance(candidates, dict) else []
    result: dict[str, list[dict]] = {}

    for group in groups:
        if not isinstance(group, dict):
            continue
        material_type = str(group.get("material_type", "")).strip() or "unknown"
        items = group.get("items", []) if isinstance(group.get("items"), list) else []
        result[material_type] = [
            {
                "material_id": item.get("material_id"),
                "name": item.get("display_name") or item.get("origin_path"),
                "category": item.get("category"),
                "role": item.get("suggested_role"),
                "zone": item.get("suggested_zone"),
                "density": item.get("density"),
                "importance": item.get("importance"),
                "preview_url": item.get("preview_url"),
                "file_url": item.get("file_url"),
            }
            for item in items
        ]

    return result


def summarize_candidate_names(candidates: dict) -> dict[str, list[dict]]:
    groups = candidates.get("groups", []) if isinstance(candidates, dict) else []
    result: dict[str, list[dict]] = {}

    for group in groups:
        if not isinstance(group, dict):
            continue
        material_type = str(group.get("material_type", "")).strip() or "unknown"
        items = group.get("items", []) if isinstance(group.get("items"), list) else []
        result[material_type] = [
            {
                "material_id": item.get("material_id"),
                "name": item.get("display_name") or item.get("origin_path"),
                "category": item.get("category"),
                "role": item.get("suggested_role"),
            }
            for item in items
        ]

    return result


def annotate_layout_suggestions(candidates: dict, *, emotion: str, scene: str, style: str) -> None:
    groups = candidates.get("groups", []) if isinstance(candidates, dict) else []
    guidance = {
        "preferred_background": None,
        "background_strategy": "solid_color",
        "selection_rule": "prefer_candidates_with_layout_suggestions",
    }

    for group in groups:
        if not isinstance(group, dict):
            continue
        material_type = str(group.get("material_type", "")).strip()
        items = group.get("items", []) if isinstance(group.get("items"), list) else []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            suggestion = build_layout_suggestion(
                material_type=material_type,
                category=str(item.get("category") or ""),
                density=str(item.get("density") or ""),
                importance=str(item.get("importance") or ""),
                background_safe=bool(item.get("background_safe")),
                emotion=emotion,
                scene=scene,
                style=style,
                index=index,
            )
            item.update(suggestion)

        if material_type == "background" and items:
            preferred = items[0]
            preferred["preferred_background"] = True
            guidance["preferred_background"] = {
                "material_id": preferred.get("material_id"),
                "name": preferred.get("display_name") or preferred.get("origin_path"),
                "preview_url": preferred.get("preview_url"),
                "file_url": preferred.get("file_url"),
                "category": preferred.get("category"),
            }
            guidance["background_strategy"] = "material_background"

    summary = candidates.get("summary", {}) if isinstance(candidates.get("summary"), dict) else {}
    summary["layout_guidance"] = guidance
    candidates["summary"] = summary


def build_layout_suggestion(
    *,
    material_type: str,
    category: str,
    density: str,
    importance: str,
    background_safe: bool,
    emotion: str,
    scene: str,
    style: str,
    index: int,
) -> dict:
    category_text = category.strip()
    scene_text = scene.strip()
    emotion_text = emotion.strip()
    style_text = style.strip().lower()

    if material_type == "background":
        return {
            "suggested_role": "background",
            "suggested_zone": "full_bleed",
            "suggested_size": "large",
            "suggested_z_index": 0,
            "background_safe": background_safe,
            "density": density,
            "importance": importance,
            "avoid_overlap_with": ["text", "date_tag", "mood_tag", "weather_tag"],
        }

    if material_type == "sticker":
        focal_match = any(token and token in f"{category_text} {scene_text} {emotion_text}" for token in ("人物场景", "动物", "海边", "咖啡", "阅读", "旅行"))
        role = "focal_sticker" if (index == 0 or focal_match or importance == "focal") and density != "high" else "supporting_sticker"
        zone = choose_sticker_zone(category_text, scene_text, role, index)
        return {
            "suggested_role": role,
            "suggested_zone": zone,
            "suggested_size": "large" if role == "focal_sticker" else "medium",
            "suggested_z_index": 22 if role == "focal_sticker" else 24 + min(index, 4),
            "density": density,
            "importance": importance,
            "avoid_overlap_with": ["text", "title", "date_tag"],
        }

    return {
        "suggested_role": "decoration",
        "suggested_zone": choose_decoration_zone(category_text, scene_text, style_text, index),
        "suggested_size": "small" if density == "high" else "medium" if "边框" in category_text or "丝带" in category_text else "small",
        "suggested_z_index": 10 + min(index, 8),
        "density": density,
        "importance": importance,
        "avoid_overlap_with": ["text", "title"],
    }


def choose_sticker_zone(category: str, scene: str, role: str, index: int) -> str:
    if role == "focal_sticker":
        if any(token in f"{category} {scene}" for token in ("人物场景", "海边", "旅行", "咖啡", "阅读")):
            return "center"
        return "lower_center"
    zones = ["top_right", "bottom_left", "bottom_right", "top_left"]
    return zones[index % len(zones)]


def choose_decoration_zone(category: str, scene: str, style: str, index: int) -> str:
    if "边框" in category:
        return "frame"
    if "丝带" in category or "标签" in category:
        return "top"
    if scene in {"海边", "旅行"} or "collage" in style:
        zones = ["top_left", "top_right", "bottom_left", "bottom_right"]
        return zones[index % len(zones)]
    return "corner"
