from __future__ import annotations

import math
from typing import Any

from app.ai.layout_v2 import ENGINE_VERSION
from app.ai.layout_v2.catalog import get_template
from app.ai.layout_v2.enums import MaterialRole
from app.ai.layout_v2.schemas import LayoutPlan, MaterialCandidate, VisualBrief
from app.config import settings


MOOD_ICONS = {
    "开心": "😊",
    "平静": "😌",
    "放松": "😮‍💨",
    "感动": "🥹",
    "兴奋": "🤩",
    "甜蜜": "🥰",
    "发呆": "🤔",
    "困倦": "😴",
    "低落": "😔",
    "难过": "😢",
    "焦虑": "😟",
    "愤怒": "😡",
}


def compile_layout_v2(
    *,
    plan: LayoutPlan,
    visual_brief: VisualBrief,
    authoritative_context: dict[str, Any],
    mood: str | dict[str, Any],
    task_id: str,
    content_text: str,
    page_width: int = 1080,
    page_height: int = 1920,
) -> dict[str, Any]:
    template = get_template(plan.template_id)
    slots = template["slots"]
    page_style = template["page_style"]
    elements: list[dict[str, Any]] = []

    for role_value in template["required_roles"]:
        candidate = plan.materials.get(role_value)
        if candidate is None:
            raise ValueError(f"missing_required_material:{role_value}")
        elements.append(_asset_element(candidate, slots[role_value], page_width, page_height))

    date_text = str(authoritative_context.get("date_text") or "").strip()
    if date_text:
        elements.append(_tag_element("date_tag", "date", date_text, "", slots["date"], page_width, page_height, page_style))

    mood_label, mood_icon = _mood_parts(mood)
    if mood_label:
        elements.append(_tag_element("mood_tag", "mood", mood_label, mood_icon, slots["mood"], page_width, page_height, page_style))

    weather_text = str(authoritative_context.get("weather_text") or "").strip()
    if authoritative_context.get("weather_success") and weather_text:
        elements.append(
            _tag_element(
                "weather_tag",
                "weather",
                weather_text,
                str(authoritative_context.get("weather_icon") or ""),
                slots["weather"],
                page_width,
                page_height,
                page_style,
                icon_key=str(authoritative_context.get("weather_icon_key") or "unknown"),
            )
        )

    elements.append(
        _text_element(
            role="title",
            content=plan.title or visual_brief.title_hint or "今天的一页",
            slot=slots["title"],
            page_width=page_width,
            page_height=page_height,
            page_style=page_style,
        )
    )
    elements.append(
        _text_element(
            role="body",
            content=content_text,
            slot=slots["body"],
            page_width=page_width,
            page_height=page_height,
            page_style=page_style,
        )
    )
    elements.sort(key=lambda item: int(item["z_index"]))
    return {
        "meta": {
            "layout_engine": "v2",
            "engine_version": ENGINE_VERSION,
            "template_id": plan.template_id,
            "template_locked": True,
            "task_id": task_id,
            "build_commit": settings.BUILD_COMMIT_SHA,
            "worker_build_commit": settings.BUILD_COMMIT_SHA,
        },
        "page": {
            "width": page_width,
            "height": page_height,
            "background": template["page"]["background"],
        },
        "elements": elements,
        "style": {
            "theme": template["themes"][0],
            "font": page_style["font"],
            "ink": page_style["ink"],
            "page_border": page_style["border"],
            "page_border_width": page_style["border_width"],
            "page_border_inset": page_style["border_inset"],
            "page_border_radius": page_style["border_radius"],
            "template_id": plan.template_id,
            "layout_type": template["layout_type"],
        },
    }


def compile_emergency_minimal_v2(*, task_id: str, input_json: dict[str, Any]) -> dict[str, Any]:
    from app.ai.layout_v2.schemas import LayoutPlan
    from app.ai.layout_v2.visual_brief import build_visual_brief

    content_text = str(input_json.get("text") or input_json.get("content_text") or "记录今日点滴")
    mood = input_json.get("mood", "")
    brief = build_visual_brief(text=content_text, mood=str(mood or ""))
    environment = input_json.get("environment_context") if isinstance(input_json.get("environment_context"), dict) else {}
    date = str(environment.get("date") or input_json.get("page_date") or "")
    weekday = str(environment.get("weekday") or "")
    weather = str(environment.get("weather") or "")
    weather_success = bool(weather and weather != "unknown")
    plan = LayoutPlan(
        template_id="minimal_text_only",
        materials={},
        title=brief.title_hint,
        score=0,
        fallback_reason="pipeline_error",
    )
    return compile_layout_v2(
        plan=plan,
        visual_brief=brief,
        authoritative_context={
            "date_text": " ".join(item for item in (date.replace("-", "."), weekday) if item),
            "weather_success": weather_success,
            "weather_text": weather if weather_success else "",
            "weather_icon": "",
            "weather_icon_key": str(environment.get("icon_key") or "unknown"),
        },
        mood=mood,
        task_id=task_id,
        content_text=content_text,
    )


def _asset_element(candidate: MaterialCandidate, slot: dict[str, Any], page_width: int, page_height: int) -> dict[str, Any]:
    x, y, width, height = _slot_box(slot, page_width, page_height)
    role = candidate.role
    element_type = (
        "image"
        if role is MaterialRole.BACKGROUND
        else "sticker"
        if role in {MaterialRole.FOCAL_STICKER, MaterialRole.SUPPORTING_STICKER}
        else "decoration"
    )
    bbox = candidate.metadata.visual_bbox.model_dump()
    return {
        "type": element_type,
        "props": {
            "id": f"{role.value}:{candidate.material_id}",
            "material_id": candidate.material_id,
            "url": candidate.file_url,
            "role": role.value,
            "x": x,
            "y": y,
            "w": width,
            "h": height,
            "rotation": float(slot.get("rotation", 0)),
            "opacity": float(slot.get("opacity", 1)),
            "fit": str(slot.get("fit") or "contain"),
            "objectPosition": str(slot.get("object_position") or "center"),
            "visualBBox": bbox,
            "cornerRadius": int(slot.get("corner_radius", 0)),
            "mask": slot.get("mask"),
            "assetWidth": candidate.asset_width,
            "assetHeight": candidate.asset_height,
            "mimeType": candidate.mime_type,
        },
        "z_index": int(slot["z_index"]),
    }


def _tag_element(
    element_type: str,
    role: str,
    text: str,
    icon: str,
    slot: dict[str, Any],
    page_width: int,
    page_height: int,
    page_style: dict[str, Any],
    **extra: Any,
) -> dict[str, Any]:
    x, y, width, height = _slot_box(slot, page_width, page_height)
    props = {
        "id": role,
        "role": role,
        "text": text,
        "content": text,
        "icon": icon,
        "x": x,
        "y": y,
        "w": width,
        "h": height,
        "font": page_style["font"],
        "fontSize": int(slot["font_size"]),
        "size": int(slot["font_size"]),
        "color": str(slot.get("color") or page_style["muted_ink"]),
        "fill": slot.get("fill"),
        "stroke": slot.get("stroke"),
        "strokeWidth": int(slot.get("stroke_width", 0)),
        "borderRadius": int(slot.get("border_radius", 0)),
        "paddingX": int(slot.get("padding_x", 0)),
        "paddingY": int(slot.get("padding_y", 0)),
        "iconGap": int(slot.get("icon_gap", 0)),
        "opacity": float(slot.get("opacity", 1)),
        "shadow": slot.get("shadow"),
        **extra,
    }
    if element_type == "date_tag":
        props["date"] = text
    elif element_type == "mood_tag":
        props["mood"] = text
    elif element_type == "weather_tag":
        props["weather"] = text
    return {"type": element_type, "props": props, "z_index": int(slot["z_index"])}


def _text_element(
    *,
    role: str,
    content: str,
    slot: dict[str, Any],
    page_width: int,
    page_height: int,
    page_style: dict[str, Any],
) -> dict[str, Any]:
    x, y, width, height = _slot_box(slot, page_width, page_height)
    size = _fit_text_size(
        content,
        width=width,
        height=height,
        base_size=int(slot["font_size"]),
        line_height=float(slot["line_height"]),
        max_lines=int(slot["max_lines"]),
    )
    return {
        "type": "text",
        "props": {
            "id": role,
            "role": role,
            "content": content,
            "x": x,
            "y": y,
            "w": width,
            "h": height,
            "size": size,
            "fontSize": size,
            "font": page_style["font"],
            "color": page_style["ink"],
            "align": str(slot.get("align") or "left"),
            "lineHeight": float(slot["line_height"]),
            "maxLines": int(slot["max_lines"]),
            "shadow": slot.get("shadow"),
        },
        "z_index": int(slot["z_index"]),
    }


def _slot_box(slot: dict[str, Any], page_width: int, page_height: int) -> tuple[int, int, int, int]:
    return (
        round(page_width * float(slot["x"])),
        round(page_height * float(slot["y"])),
        round(page_width * float(slot["w"])),
        round(page_height * float(slot["h"])),
    )


def _fit_text_size(content: str, *, width: int, height: int, base_size: int, line_height: float, max_lines: int) -> int:
    minimum = 30 if base_size < 56 else 44
    size = base_size
    while size > minimum:
        estimated_lines = _estimated_line_count(content, width=width, font_size=size)
        if estimated_lines <= max_lines and estimated_lines * size * line_height <= height:
            return size
        size -= 2
    return minimum


def _estimated_line_count(content: str, *, width: int, font_size: int) -> int:
    capacity = max(1, math.floor(width / max(1, font_size * 0.92)))
    return sum(max(1, math.ceil(len(line) / capacity)) for line in str(content or "").splitlines() or [""])


def _mood_parts(mood: str | dict[str, Any]) -> tuple[str, str]:
    if isinstance(mood, dict):
        label = str(mood.get("label") or mood.get("mood") or "").strip()
        return label, str(mood.get("icon") or MOOD_ICONS.get(label, "")).strip()
    label = str(mood or "").strip()
    return label, MOOD_ICONS.get(label, "")
