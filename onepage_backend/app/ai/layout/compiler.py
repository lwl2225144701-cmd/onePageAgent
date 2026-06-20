from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.ai.layout.template_specs import get_template_spec


PAGE_WIDTH = 1080
PAGE_HEIGHT = 1920
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


def compile_layout_template(
    *,
    template_id: str,
    title: str,
    body: str,
    mood: str | dict[str, Any],
    authoritative_context: dict[str, Any],
    selected_materials: dict[str, Any],
    style: dict[str, Any] | None = None,
    optional_slots: dict[str, bool] | None = None,
) -> dict[str, Any]:
    spec = deepcopy(get_template_spec(template_id))
    page_style = spec["page_style"]
    slots = spec["slots"]
    optional_slots = _resolve_optional_slots(spec, optional_slots)
    elements: list[dict[str, Any]] = []

    _append_material_slot(elements, slots, "background", selected_materials.get("background"), optional_slots, required=_required(spec, "background"))
    _append_material_slot(elements, slots, "frame", selected_materials.get("frame"), optional_slots, required=_required(spec, "frame"))
    _append_material_slot(elements, slots, "tape", selected_materials.get("tape"), optional_slots, required=_required(spec, "tape"))

    date_text = str(authoritative_context.get("date_text") or "").strip()
    if date_text and "date" in slots:
        elements.append(_tag_element("date_tag", "date", slots["date"], date=date_text, color=page_style["muted_ink"]))

    mood_label, mood_icon = _mood_parts(mood)
    if mood_label and "mood" in slots:
        elements.append(
            _tag_element("mood_tag", "mood", slots["mood"], mood=mood_label, icon=mood_icon, color=page_style["muted_ink"])
        )

    weather_text = str(authoritative_context.get("weather_text") or "").strip()
    if authoritative_context.get("weather_success") and weather_text and "weather" in slots:
        elements.append(
            _tag_element(
                "weather_tag",
                "weather",
                slots["weather"],
                weather=weather_text,
                icon=str(authoritative_context.get("weather_icon") or ""),
                icon_key=str(authoritative_context.get("weather_icon_key") or "unknown"),
                color=page_style["muted_ink"],
            )
        )

    elements.append(_text_element("title", title or "今天的一页", slots["title"], page_style, is_title=True))
    _append_material_slot(
        elements,
        slots,
        "focal_sticker",
        selected_materials.get("focal_sticker"),
        optional_slots,
        required=_required(spec, "focal_sticker"),
    )

    supporting = selected_materials.get("supporting_stickers") or []
    if isinstance(supporting, list) and supporting:
        _append_material_slot(elements, slots, "supporting_sticker", supporting[0], optional_slots, required=False)

    decorations = selected_materials.get("decorations") or []
    if isinstance(decorations, list) and decorations:
        _append_material_slot(elements, slots, "decoration", decorations[0], optional_slots, required=False)

    elements.append(_text_element("body", body, slots["body"], page_style, is_title=False))
    elements.sort(key=lambda item: int(item.get("z_index", 0)))
    theme = str((style or {}).get("theme") or spec["themes"][0])
    if theme not in {"healing", "warm", "vintage", "minimal", "cute", "cool", "elegant", "vivid", "calm"}:
        theme = spec["themes"][0]
    return {
        "template_id": template_id,
        "page": {"width": PAGE_WIDTH, "height": PAGE_HEIGHT, "background": page_style["background"]},
        "elements": elements,
        "style": {
            "theme": theme,
            "font": page_style["font"],
            "ink": page_style["ink"],
            "page_border": "#E5D8C7",
            "page_border_width": 3,
            "page_border_inset": 24,
            "template_id": template_id,
            "layout_type": spec["layout_type"],
        },
    }


def _append_material_slot(
    elements: list[dict[str, Any]],
    slots: dict[str, dict[str, Any]],
    slot_name: str,
    material: object,
    decisions: dict[str, bool],
    *,
    required: bool,
) -> None:
    if slot_name not in slots or not isinstance(material, dict):
        return
    if not required and not decisions.get(slot_name, False):
        return
    if slot_name == "background" and material.get("background_safe") is False:
        return
    material_id = str(material.get("material_id") or "").strip()
    url = _material_url(material)
    if not material_id or not url:
        return

    slot = slots[slot_name]
    x, y, width, height = _slot_box(slot)
    if slot_name != "frame":
        width, height, x, y = _fit_material(material, width=width, height=height, x=x, y=y)
    element_type = "image" if slot_name == "background" else "sticker" if "sticker" in slot_name else "decoration"
    elements.append(
        {
            "type": element_type,
            "props": {
                "id": f"{slot_name}:{material_id}",
                "material_id": material_id,
                "url": url,
                "role": slot_name,
                "x": x,
                "y": y,
                "w": width,
                "h": height,
                "opacity": float(slot.get("opacity", 1)),
                "fit": "contain",
            },
            "z_index": int(slot["z"]),
        }
    )


def _text_element(role: str, content: str, slot: dict[str, Any], page_style: dict[str, Any], *, is_title: bool) -> dict[str, Any]:
    x, y, width, height = _slot_box(slot)
    base_size = int(slot["size"])
    size = _fit_text_size(str(content or ""), width=width, height=height, base_size=base_size, line_height=float(slot.get("line_height", 1.45)))
    return {
        "type": "text",
        "props": {
            "id": role,
            "role": role,
            "content": str(content or ""),
            "x": x,
            "y": y,
            "w": width,
            "h": height,
            "size": size,
            "lineHeight": float(slot.get("line_height", 1.45)),
            "color": page_style["ink"],
            "font": page_style["font"],
            "align": "left",
            "max_lines": 2 if is_title else None,
        },
        "z_index": int(slot["z"]),
    }


def _tag_element(element_type: str, slot_name: str, slot: dict[str, Any], **content: Any) -> dict[str, Any]:
    x, y, width, height = _slot_box(slot)
    return {
        "type": element_type,
        "props": {
            "id": slot_name,
            "x": x,
            "y": y,
            "w": width,
            "h": height,
            "size": int(slot["size"]),
            "font": "handwriting",
            **content,
        },
        "z_index": int(slot["z"]),
    }


def _slot_box(slot: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        round(PAGE_WIDTH * float(slot["x"])),
        round(PAGE_HEIGHT * float(slot["y"])),
        round(PAGE_WIDTH * float(slot["w"])),
        round(PAGE_HEIGHT * float(slot["h"])),
    )


def _fit_material(material: dict[str, Any], *, width: int, height: int, x: int, y: int) -> tuple[int, int, int, int]:
    try:
        ratio = float(material.get("asset_width") or 0) / float(material.get("asset_height") or 0)
    except (TypeError, ValueError, ZeroDivisionError):
        ratio = 0
    if ratio <= 0:
        return width, height, x, y
    slot_ratio = width / max(1, height)
    if ratio > slot_ratio:
        fitted_height = max(1, round(width / ratio))
        return width, fitted_height, x, y + round((height - fitted_height) / 2)
    fitted_width = max(1, round(height * ratio))
    return fitted_width, height, x + round((width - fitted_width) / 2), y


def _fit_text_size(content: str, *, width: int, height: int, base_size: int, line_height: float) -> int:
    size = base_size
    minimum = 42 if base_size >= 56 else 28
    while size > minimum:
        chars_per_line = max(1, int(width / max(1, size * 0.9)))
        lines = sum(max(1, (len(line) + chars_per_line - 1) // chars_per_line) for line in content.split("\n"))
        if lines * size * line_height <= height:
            break
        size -= 2
    return size


def _mood_parts(mood: str | dict[str, Any]) -> tuple[str, str]:
    if isinstance(mood, dict):
        label = str(mood.get("label") or mood.get("mood") or "").strip()
        return label, str(mood.get("icon") or MOOD_ICONS.get(label, "")).strip()
    label = str(mood or "").strip()
    return label, MOOD_ICONS.get(label, "")


def _material_url(material: dict[str, Any]) -> str:
    for key in ("file_url", "preview_url", "raw_file_url", "url"):
        value = str(material.get(key) or "").strip()
        if value:
            return value
    return ""


def _required(spec: dict[str, Any], role: str) -> bool:
    return role in set(spec.get("required_roles", []))


def _resolve_optional_slots(
    spec: dict[str, Any],
    decisions: dict[str, bool] | None,
) -> dict[str, bool]:
    provided = decisions if isinstance(decisions, dict) else {}
    defaults = spec.get("default_optional_slots")
    defaults = defaults if isinstance(defaults, dict) else {}
    optional_roles = set(spec.get("optional_roles", []))
    resolved: dict[str, bool] = {}
    for role in optional_roles:
        value = provided.get(role)
        if isinstance(value, bool):
            resolved[role] = value
            continue
        default = defaults.get(role)
        resolved[role] = default if isinstance(default, bool) else False
    return resolved
