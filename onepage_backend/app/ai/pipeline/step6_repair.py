import json
import structlog

from app.ai.fallback.repairer import LayoutRepairer
from app.ai.fallback.templates import get_fallback_layout
from app.ai.fallback.validator import LayoutValidator

logger = structlog.get_logger(__name__)


async def run_validate_and_repair(ctx: dict) -> dict:
    """Step 6: Validate, repair, or fallback the Layout JSON."""
    raw_json = ctx.get("step5", "{}")
    step4 = ctx.get("step4_review") or ctx.get("step4", {})
    input_json = ctx.get("input_json", {})
    selection_enforced = isinstance(step4, dict) and "selected_materials" in step4
    asset_context = {
        "groups": step4.get("groups", []) if isinstance(step4, dict) else [],
        "fallback_mode": step4.get("fallback_mode", "none") if isinstance(step4, dict) else "none",
        "selected_materials": step4.get("selected_materials", []) if isinstance(step4, dict) else [],
        "selection_enforced": selection_enforced,
        "rejected_materials": step4.get("rejected_materials", []) if isinstance(step4, dict) else [],
        "input_image_urls": input_json.get("image_urls", []) if isinstance(input_json, dict) else [],
    }

    validator = LayoutValidator()
    repairer = LayoutRepairer()
    compiled_template_id = _compiled_template_id(raw_json)

    repaired = (
        repairer.repair_conservative(raw_json, asset_context=asset_context)
        if compiled_template_id
        else repairer.repair(raw_json, [], asset_context=asset_context)
    )
    if repaired is not None:
        repaired = apply_semantic_guard(repaired, ctx=ctx, asset_context=asset_context)
        repaired = apply_fact_field_normalization(repaired, ctx=ctx)
        repaired = apply_final_page_quality_check(repaired, ctx=ctx, asset_context=asset_context)
        errors = validator.validate(repaired, asset_context=asset_context)
        print(
            "ONEPAGE_LAYOUT_VALIDATED "
            f"task_id={ctx.get('task_id')} errors={json.dumps(errors, ensure_ascii=False)} pass={str(not errors).lower()}",
            flush=True,
        )
        if not errors:
            print(
                f"ONEPAGE_LAYOUT_REPAIRED task_id={ctx.get('task_id')} "
                f"mode={'template_conservative' if compiled_template_id else 'single_pass'} "
                f"template_id={compiled_template_id or ''} "
                f"actions={'schema,asset_allowlist,bounds,fact_fields' if compiled_template_id else 'asset_allowlist,aspect_ratio,bounds,overlap,readability,fact_fields'}",
                flush=True,
            )
            return repaired
        logger.warning("step6_validation_errors", errors=errors)

    # If repair didn't fully fix, try re-repairing with errors list
    if repaired is not None:
        errors = validator.validate(repaired, asset_context=asset_context)
        repaired2 = (
            repairer.repair_conservative(json.dumps(repaired, ensure_ascii=False), asset_context=asset_context)
            if compiled_template_id
            else repairer.repair(json.dumps(repaired, ensure_ascii=False), errors, asset_context=asset_context)
        )
        if repaired2 is not None:
            repaired2 = apply_semantic_guard(repaired2, ctx=ctx, asset_context=asset_context)
            repaired2 = apply_fact_field_normalization(repaired2, ctx=ctx)
            repaired2 = apply_final_page_quality_check(repaired2, ctx=ctx, asset_context=asset_context)
            errors2 = validator.validate(repaired2, asset_context=asset_context)
            print(
                "ONEPAGE_LAYOUT_VALIDATED "
                f"task_id={ctx.get('task_id')} errors={json.dumps(errors2, ensure_ascii=False)} pass={str(not errors2).lower()}",
                flush=True,
            )
            if not errors2:
                print(
                    f"ONEPAGE_LAYOUT_REPAIRED task_id={ctx.get('task_id')} mode=second_pass "
                    f"actions={json.dumps(errors, ensure_ascii=False)}",
                    flush=True,
                )
                return repaired2

    # Ultimate fallback
    emotion = ctx.get("step2", {}).get("primary_emotion", "neutral")
    content_text = input_json.get("text", "") or input_json.get("content_text", "")
    journal_context = ctx.get("journal_context", {}) if isinstance(ctx.get("journal_context"), dict) else {}
    page_date = _journal_date_text(journal_context)
    logger.warning(
        "step6_fallback_used",
        emotion=emotion,
        candidate_group_counts={group.get("material_type"): len(group.get("items", [])) for group in asset_context["groups"]},
        image_url_count=len(asset_context["input_image_urls"]),
    )
    fallback_layout = get_fallback_layout(emotion, content_text=content_text, page_date=page_date)
    repaired_fallback = repairer.repair(json.dumps(fallback_layout, ensure_ascii=False), [], asset_context=asset_context)
    if repaired_fallback is not None:
        repaired_fallback = apply_semantic_guard(repaired_fallback, ctx=ctx, asset_context=asset_context)
        repaired_fallback = apply_fact_field_normalization(repaired_fallback, ctx=ctx)
        print(
            f"ONEPAGE_LAYOUT_REPAIRED task_id={ctx.get('task_id')} mode=fallback "
            "actions=fallback_layout,asset_allowlist,fact_fields",
            flush=True,
        )
        return apply_final_page_quality_check(repaired_fallback, ctx=ctx, asset_context=asset_context)
    fallback_layout = apply_fact_field_normalization(fallback_layout, ctx=ctx)
    print(f"ONEPAGE_LAYOUT_REPAIRED task_id={ctx.get('task_id')} mode=fallback_raw", flush=True)
    return apply_final_page_quality_check(fallback_layout, ctx=ctx, asset_context=asset_context)


def _compiled_template_id(raw_json: object) -> str:
    if not isinstance(raw_json, str):
        return ""
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    style = payload.get("style") if isinstance(payload.get("style"), dict) else {}
    return str(payload.get("template_id") or style.get("template_id") or "").strip()


SEMANTIC_GUARD_SCENES = {"self_growth", "study_reflection", "exam_prep", "work"}
SEMANTIC_GUARD_RISKS = {
    "valentine",
    "romance",
    "wedding",
    "party",
    "festival_text",
    "unrelated_people",
}
SEMANTIC_GUARD_TOKENS = (
    "valentine",
    "happy valentine",
    "情人节",
    "恋爱",
    "情侣",
    "婚礼",
    "婚纱",
    "wedding",
    "romance",
    "party",
    "派对",
    "节日快乐",
    "festival",
)
FOOD_SEMANTIC_GUARD_RISKS = {
    "party",
    "family",
    "dance",
    "ballet",
    "religion",
    "crest",
    "valentine",
    "wedding",
    "romance",
    "congratulations",
    "gift",
    "bouquet",
    "festival_text",
    "unrelated_people",
}
FOOD_SEMANTIC_GUARD_TOKENS = (
    "party",
    "family",
    "ballet",
    "dance",
    "dancing",
    "running",
    "japanese family crest",
    "family crest",
    "chidori",
    "buddha",
    "boxer",
    "valentine",
    "wedding",
    "romance",
    "congratulations",
    "congrats",
    "celebration",
    "gift",
    "bouquet",
    "おめでとう",
    "祝福",
    "派对",
    "情人节",
    "婚礼",
    "恋爱",
    "花束",
    "礼物",
    "家紋",
    "千鳥",
    "芭蕾",
    "舞蹈",
    "人物场景",
)


def apply_semantic_guard(layout: dict, *, ctx: dict, asset_context: dict) -> dict:
    """Final safety pass: keep manual-compatible layout JSON but remove semantic mismatches."""

    if not isinstance(layout, dict):
        return layout
    step1 = ctx.get("step1", {}) if isinstance(ctx, dict) else {}
    semantic = _semantic_fields(step1)
    protected = (
        semantic["scene"] in SEMANTIC_GUARD_SCENES
        or semantic["sub_scene"] in SEMANTIC_GUARD_SCENES
        or semantic["intent"] in SEMANTIC_GUARD_SCENES
    )
    url_map = _candidate_by_url(asset_context)
    elements = layout.get("elements")
    if not isinstance(elements, list):
        return layout

    kept: list[dict] = []
    removed: list[dict] = []
    food_removed: list[dict] = []
    empty_removed: list[dict] = []
    for element in elements:
        if not isinstance(element, dict):
            kept.append(element)
            continue
        props = element.get("props", {}) if isinstance(element.get("props"), dict) else {}
        url = str(props.get("url") or "").strip()
        candidate = url_map.get(url) if url else None
        risks = set(candidate.get("risk_flags") or []) if isinstance(candidate, dict) else set()
        text = " ".join(
            str(value or "")
            for value in (
                url,
                candidate.get("display_name") if isinstance(candidate, dict) else "",
                candidate.get("name") if isinstance(candidate, dict) else "",
                candidate.get("category") if isinstance(candidate, dict) else "",
                candidate.get("review_reason") if isinstance(candidate, dict) else "",
                props.get("content"),
            )
        ).lower()
        remove_reason = ""
        if protected and (risks.intersection(SEMANTIC_GUARD_RISKS) or _contains_any(text, SEMANTIC_GUARD_TOKENS)):
            remove_reason = "semantic_risk_for_study_or_work"
        if semantic["sub_scene"] == "food_review" and (
            risks.intersection(FOOD_SEMANTIC_GUARD_RISKS) or _contains_any(text, FOOD_SEMANTIC_GUARD_TOKENS)
        ):
            remove_reason = "food_review_semantic_risk"
        if element.get("type") == "image" and _is_unsafe_background(candidate, props):
            remove_reason = "unsafe_background"
        if not remove_reason and _is_empty_visual_block(element, layout):
            remove_reason = "empty_visual_block"

        if remove_reason:
            removed_item = {"url": url, "type": element.get("type"), "reason": remove_reason}
            removed.append(removed_item)
            if remove_reason == "food_review_semantic_risk":
                food_removed.append(removed_item)
            elif remove_reason == "empty_visual_block":
                empty_removed.append(removed_item)
            continue
        kept.append(element)

    if removed:
        layout = dict(layout)
        layout["elements"] = kept
        page = layout.get("page") if isinstance(layout.get("page"), dict) else {}
        if not page.get("background"):
            page["background"] = "#FAF6F0"
            layout["page"] = page
        print(
            f"STEP6_SEMANTIC_GUARD task_id={ctx.get('task_id')} removed={json.dumps(removed, ensure_ascii=False)} reason=semantic_or_background_risk",
            flush=True,
        )
        if food_removed:
            print(
                f"STEP6_FOOD_SEMANTIC_GUARD task_id={ctx.get('task_id')} removed={json.dumps(food_removed, ensure_ascii=False)} reason=food_review_semantic_risk",
                flush=True,
            )
        if empty_removed:
            print(
                f"STEP6_EMPTY_BLOCK_GUARD task_id={ctx.get('task_id')} removed={json.dumps(empty_removed, ensure_ascii=False)} reason=empty_visual_block",
                flush=True,
            )
    return layout


def apply_fact_field_normalization(layout: dict, *, ctx: dict) -> dict:
    """Bind date/weather tags to authoritative journal context after model repair."""

    if not isinstance(layout, dict):
        return layout
    elements = layout.get("elements")
    if not isinstance(elements, list):
        return layout

    journal_context = ctx.get("journal_context", {}) if isinstance(ctx, dict) and isinstance(ctx.get("journal_context"), dict) else {}
    date_text = _journal_date_text(journal_context)
    weather_text = _journal_weather_text(journal_context)
    weather_icon = _journal_weather_icon(journal_context)
    weather_icon_key = _journal_weather_icon_key(journal_context)
    weather_success = bool(journal_context.get("weather_success") and weather_text)
    if not date_text:
        return layout

    layout = dict(layout)
    normalized_elements: list[dict] = []
    has_date = False
    has_weather = False
    date_overridden = 0
    weather_overridden = 0

    for element in elements:
        if not isinstance(element, dict):
            normalized_elements.append(element)
            continue
        el_type = element.get("type")
        props = element.get("props", {}) if isinstance(element.get("props"), dict) else {}
        if el_type == "date_tag":
            has_date = True
            next_element = dict(element)
            next_props = dict(props)
            before = (next_props.get("date"), next_props.get("text"), next_props.get("content"))
            next_props["date"] = date_text
            next_props["text"] = date_text
            if "content" in next_props:
                next_props["content"] = date_text
            if before != (next_props.get("date"), next_props.get("text"), next_props.get("content")):
                date_overridden += 1
            next_element["props"] = next_props
            normalized_elements.append(next_element)
            continue
        if el_type == "weather_tag":
            if not weather_success:
                weather_overridden += 1
                continue
            has_weather = True
            next_element = dict(element)
            next_props = dict(props)
            before = (
                next_props.get("weather"),
                next_props.get("text"),
                next_props.get("content"),
                next_props.get("icon"),
                next_props.get("icon_key"),
            )
            next_props["weather"] = weather_text
            next_props["text"] = weather_text
            if "content" in next_props:
                next_props["content"] = weather_text
            next_props["icon"] = weather_icon
            next_props["icon_key"] = weather_icon_key
            after = (
                next_props.get("weather"),
                next_props.get("text"),
                next_props.get("content"),
                next_props.get("icon"),
                next_props.get("icon_key"),
            )
            if before != after:
                weather_overridden += 1
            next_element["props"] = next_props
            normalized_elements.append(next_element)
            continue
        normalized_elements.append(element)

    page = layout.get("page", {}) if isinstance(layout.get("page"), dict) else {}
    page_width = _positive_number(page.get("width"), 1080)
    page_height = _positive_number(page.get("height"), 1920)
    base_x = round(page_width * 0.074)
    base_y = round(page_height * 0.052)
    tag_gap_y = round(page_height * 0.026)
    tag_gap_x = round(page_width * 0.12)

    if not has_date:
        normalized_elements.append(
            {
                "type": "date_tag",
                "props": {
                    "date": date_text,
                    "text": date_text,
                    "font": "handwriting",
                    "size": 28,
                    "color": "#8B7D6B",
                    "x": base_x,
                    "y": base_y,
                },
                "z_index": 40,
            }
        )
        date_overridden += 1

    if weather_success and not has_weather:
        normalized_elements.append(
            {
                "type": "weather_tag",
                "props": {
                    "weather": weather_text,
                    "text": weather_text,
                    "icon": weather_icon,
                    "icon_key": weather_icon_key,
                    "x": base_x + tag_gap_x,
                    "y": base_y + tag_gap_y,
                },
                "z_index": 40,
            }
        )
        weather_overridden += 1

    layout["elements"] = normalized_elements
    print(
        "STEP6_FACT_FIELDS_NORMALIZED "
        f"task_id={ctx.get('task_id')} "
        f"date_overridden={date_overridden} "
        f"weather_overridden={weather_overridden}",
        flush=True,
    )
    return layout


def apply_final_page_quality_check(layout: dict, *, ctx: dict, asset_context: dict) -> dict:
    if not isinstance(layout, dict):
        return layout
    elements = layout.get("elements")
    if not isinstance(elements, list):
        return layout

    page = layout.get("page", {}) if isinstance(layout.get("page"), dict) else {}
    page_width = _positive_number(page.get("width"), 1080)
    page_height = _positive_number(page.get("height"), 1920)
    page_area = max(1.0, page_width * page_height)
    candidates_by_url = _candidate_by_url(asset_context)
    rejected_by_url = _rejected_by_url(ctx)
    selected_ids, selected_urls = _selected_material_allowlist(asset_context)
    journal_context = ctx.get("journal_context", {}) if isinstance(ctx, dict) and isinstance(ctx.get("journal_context"), dict) else {}
    weather_success = bool(journal_context.get("weather_success"))
    weather_status = str(journal_context.get("weather_status") or ("success" if weather_success else "unavailable"))

    kept: list[dict] = []
    failed_asset_count = 0
    rejected_used_count = 0
    focal_sticker_count = 0
    weather_visible = False

    for element in elements:
        if not isinstance(element, dict):
            kept.append(element)
            continue
        element_type = str(element.get("type") or "")
        props = element.get("props", {}) if isinstance(element.get("props"), dict) else {}
        url = str(props.get("url") or "").strip()
        material_id = str(props.get("material_id") or "").strip()

        if element_type in {"image", "sticker", "decoration"}:
            if not url:
                failed_asset_count += 1
                continue
            if url in rejected_by_url:
                rejected_used_count += 1
                continue
            if selected_urls and url not in selected_urls and url not in asset_context.get("input_image_urls", []):
                failed_asset_count += 1
                continue
            if selected_ids and material_id not in selected_ids and url not in asset_context.get("input_image_urls", []):
                failed_asset_count += 1
                continue

            candidate = candidates_by_url.get(url)
            role = str((candidate or {}).get("safe_role") or (candidate or {}).get("suggested_role") or "")
            review_decision = str((candidate or {}).get("review_decision") or (candidate or {}).get("decision") or "")
            area_ratio = _element_area_ratio(props, page_area)
            if review_decision == "downgrade" and (element_type == "image" or role == "texture_accent" or area_ratio > 0.18):
                failed_asset_count += 1
                continue
            if role == "focal_sticker":
                if focal_sticker_count >= 1:
                    failed_asset_count += 1
                    continue
                focal_sticker_count += 1

        if element_type == "weather_tag":
            if not weather_success:
                failed_asset_count += 1
                continue
            weather_visible = True

        kept.append(element)

    layout = dict(layout)
    layout["elements"] = kept
    material_count = sum(
        1
        for element in kept
        if isinstance(element, dict)
        and str(element.get("type") or "") in {"image", "sticker", "decoration"}
        and isinstance(element.get("props"), dict)
        and str(element.get("props", {}).get("url") or "").strip()
    )
    passed = failed_asset_count == 0 and rejected_used_count == 0 and focal_sticker_count <= 1 and (weather_success or not weather_visible)
    print(
        "FINAL_PAGE_QUALITY_CHECK "
        f"task_id={ctx.get('task_id')} "
        f"element_count={len(kept)} "
        f"material_count={material_count} "
        f"failed_asset_count={failed_asset_count} "
        f"rejected_material_used_count={rejected_used_count} "
        f"focal_sticker_count={focal_sticker_count} "
        f"weather_status={weather_status} "
        f"weather_visible={str(weather_visible).lower()} "
        f"passed={str(passed).lower()}",
        flush=True,
    )
    return layout


def _semantic_fields(step1: dict) -> dict:
    text_analysis = step1.get("text_analysis", {}) if isinstance(step1.get("text_analysis"), dict) else {}
    return {
        "scene": str(step1.get("scene") or text_analysis.get("scene") or ""),
        "sub_scene": str(step1.get("sub_scene") or text_analysis.get("sub_scene") or ""),
        "intent": str(step1.get("intent") or text_analysis.get("intent") or ""),
    }


def _journal_date_text(journal_context: dict) -> str:
    header = journal_context.get("journal_header", {}) if isinstance(journal_context.get("journal_header"), dict) else {}
    datetime_context = journal_context.get("datetime", {}) if isinstance(journal_context.get("datetime"), dict) else {}
    date_text = str(header.get("date_text") or datetime_context.get("date") or "").strip()
    if date_text:
        return date_text
    from app.ai.mcp_client import build_system_datetime_context

    return build_system_datetime_context("Asia/Shanghai")["date"]


def _journal_weather_text(journal_context: dict) -> str:
    if not journal_context.get("weather_success"):
        return ""
    header = journal_context.get("journal_header", {}) if isinstance(journal_context.get("journal_header"), dict) else {}
    weather_context = journal_context.get("weather", {}) if isinstance(journal_context.get("weather"), dict) else {}
    return str(header.get("weather_text") or weather_context.get("text") or "").strip()


def _journal_weather_icon(journal_context: dict) -> str:
    if not journal_context.get("weather_success"):
        return ""
    header = journal_context.get("journal_header", {}) if isinstance(journal_context.get("journal_header"), dict) else {}
    weather_context = journal_context.get("weather", {}) if isinstance(journal_context.get("weather"), dict) else {}
    return str(header.get("weather_icon") or weather_context.get("icon") or "").strip()


def _journal_weather_icon_key(journal_context: dict) -> str:
    if not journal_context.get("weather_success"):
        return ""
    weather_context = journal_context.get("weather", {}) if isinstance(journal_context.get("weather"), dict) else {}
    return str(weather_context.get("icon_key") or "").strip()


def _positive_number(value, fallback: float) -> float:
    try:
        number = float(value)
        return number if number > 0 else fallback
    except Exception:
        return fallback


def _candidate_by_url(asset_context: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for group in asset_context.get("groups", []) if isinstance(asset_context, dict) else []:
        if not isinstance(group, dict):
            continue
        for item in group.get("items", []) if isinstance(group.get("items"), list) else []:
            if not isinstance(item, dict):
                continue
            for key in ("file_url", "preview_url", "raw_file_url"):
                url = str(item.get(key) or "").strip()
                if url:
                    result[url] = item
    return result


def _rejected_by_url(ctx: dict) -> dict[str, dict]:
    step4 = ctx.get("step4_review") or ctx.get("step4") or {}
    result: dict[str, dict] = {}
    for item in step4.get("rejected_materials", []) if isinstance(step4, dict) and isinstance(step4.get("rejected_materials"), list) else []:
        if not isinstance(item, dict):
            continue
        for key in ("file_url", "preview_url", "raw_file_url"):
            url = str(item.get(key) or "").strip()
            if url:
                result[url] = item
    return result


def _selected_material_allowlist(asset_context: dict) -> tuple[set[str], set[str]]:
    if not asset_context.get("selection_enforced"):
        return set(), set()
    selected_ids: set[str] = set()
    selected_urls: set[str] = set()
    for item in asset_context.get("selected_materials", []) if isinstance(asset_context, dict) else []:
        if not isinstance(item, dict):
            continue
        material_id = str(item.get("material_id") or "").strip()
        if material_id:
            selected_ids.add(material_id)
        for key in ("file_url", "preview_url", "raw_file_url"):
            url = str(item.get(key) or "").strip()
            if url:
                selected_urls.add(url)
    return selected_ids, selected_urls


def _element_area_ratio(props: dict, page_area: float) -> float:
    try:
        width = float(props.get("w") or props.get("width") or 0)
        height = float(props.get("h") or props.get("height") or 0)
    except Exception:
        return 0.0
    return max(0.0, width * height / max(1.0, page_area))


def _is_unsafe_background(candidate: dict | None, props: dict) -> bool:
    if not isinstance(candidate, dict):
        return False
    flags = set(candidate.get("risk_flags") or [])
    if flags.intersection({"unsafe_background", "strong_pattern", "too_dense"}):
        return True
    if candidate.get("background_safe") is False:
        return True
    try:
        w = float(props.get("w") or 0)
        h = float(props.get("h") or 0)
    except Exception:
        w = h = 0
    is_large = w >= 800 or h >= 900
    try:
        background_safety = float(candidate.get("background_safety"))
    except Exception:
        background_safety = 1.0
    return is_large and background_safety < 0.5


def _is_empty_visual_block(element: dict, layout: dict) -> bool:
    element_type = str(element.get("type") or "")
    if element_type not in {"note_card", "decoration", "shape", "block"}:
        return False
    props = element.get("props", {}) if isinstance(element.get("props"), dict) else {}
    if any(str(props.get(key) or "").strip() for key in ("content", "text", "date", "mood", "weather", "url", "icon", "label")):
        return False
    page = layout.get("page", {}) if isinstance(layout.get("page"), dict) else {}
    try:
        page_width = float(page.get("width") or 0)
        page_height = float(page.get("height") or 0)
        if page_width <= 0 or page_height <= 0:
            return False
        page_area = page_width * page_height
        area = float(props.get("w") or props.get("width") or 0) * float(props.get("h") or props.get("height") or 0)
    except Exception:
        area = 0
    visual_fill = any(str(props.get(key) or "").strip() for key in ("background", "backgroundColor", "fill", "color", "borderColor"))
    return visual_fill and area / page_area >= 0.01


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(token.lower() in lowered for token in tokens)
