from __future__ import annotations

import math
from typing import Any
from urllib.parse import urlparse

from app.ai.layout_v2.catalog import get_template
from app.ai.layout_v2.schemas import LayoutPlan


def validate_layout_v2(
    layout: dict[str, Any],
    *,
    plan: LayoutPlan,
    authoritative_context: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
    if meta.get("layout_engine") != "v2":
        errors.append("layout_engine_not_v2")
    if meta.get("template_id") != plan.template_id:
        errors.append("template_id_mismatch")
    try:
        template = get_template(plan.template_id)
    except KeyError:
        return [*errors, "unknown_template_id"]

    page = layout.get("page") if isinstance(layout.get("page"), dict) else {}
    width = _number(page.get("width"))
    height = _number(page.get("height"))
    if width is None or height is None or width <= 0 or height <= 0:
        return [*errors, "invalid_page_size"]
    elements = layout.get("elements") if isinstance(layout.get("elements"), list) else []
    seen_roles: dict[str, dict[str, Any]] = {}
    expected_roles = set(template["required_roles"])
    for element in elements:
        if not isinstance(element, dict) or not isinstance(element.get("props"), dict):
            errors.append("invalid_element")
            continue
        props = element["props"]
        role = str(props.get("role") or "")
        if role in {"background", "focal_sticker", "supporting_sticker", "tape", "frame", "decoration"}:
            if role not in expected_roles:
                errors.append(f"role_not_defined_by_template:{role}")
            if role in seen_roles:
                errors.append(f"duplicate_role:{role}")
            seen_roles[role] = element
            _validate_material_binding(errors, role, props, plan)
        if role in template["slots"]:
            _validate_template_slot(errors, element, template["slots"][role], width, height)
        _validate_bounds(errors, props, width, height)
        _validate_visual_bbox(errors, props)

    for role in expected_roles:
        if role not in seen_roles:
            errors.append(f"missing_required_role:{role}")

    date_element = _element_by_type(elements, "date_tag")
    expected_date = str(authoritative_context.get("date_text") or "")
    if expected_date and str((date_element or {}).get("props", {}).get("date") or "") != expected_date:
        errors.append("authoritative_date_mismatch")
    weather_element = _element_by_type(elements, "weather_tag")
    if authoritative_context.get("weather_success"):
        expected_weather = str(authoritative_context.get("weather_text") or "")
        if expected_weather and str((weather_element or {}).get("props", {}).get("weather") or "") != expected_weather:
            errors.append("authoritative_weather_mismatch")
    elif weather_element is not None:
        errors.append("weather_present_without_success")
    _validate_forbidden_overlaps(errors, elements, template)
    return errors


def _validate_template_slot(
    errors: list[str],
    element: dict[str, Any],
    slot: dict[str, Any],
    page_width: float,
    page_height: float,
) -> None:
    props = element["props"]
    role = str(props.get("role") or "")
    expected = {
        "x": round(page_width * float(slot["x"])),
        "y": round(page_height * float(slot["y"])),
        "w": round(page_width * float(slot["w"])),
        "h": round(page_height * float(slot["h"])),
    }
    if any(abs(float(props.get(key, -10_000)) - value) > 1 for key, value in expected.items()):
        errors.append(f"template_slot_geometry_mismatch:{role}")
    if int(element.get("z_index", -1)) != int(slot["z_index"]):
        errors.append(f"template_slot_z_index_mismatch:{role}")
    if role in {"background", "focal_sticker", "supporting_sticker", "tape", "frame", "decoration"}:
        if str(props.get("fit") or "contain") != str(slot.get("fit") or "contain"):
            errors.append(f"template_slot_fit_mismatch:{role}")
        if abs(float(props.get("opacity", 1)) - float(slot.get("opacity", 1))) > 0.001:
            errors.append(f"template_slot_opacity_mismatch:{role}")


def _validate_forbidden_overlaps(errors: list[str], elements: list[Any], template: dict[str, Any]) -> None:
    by_role = {
        str(item.get("props", {}).get("role") or ""): item
        for item in elements
        if isinstance(item, dict) and isinstance(item.get("props"), dict)
    }
    pairs = [
        ("date", "mood"),
        ("date", "weather"),
        ("mood", "weather"),
        *template["render_rules"].get("forbidden_overlaps", []),
    ]
    for first, second in pairs:
        if "frame" in {first, second}:
            continue
        if first in by_role and second in by_role and _overlap_ratio(by_role[first]["props"], by_role[second]["props"]) > 0.01:
            errors.append(f"forbidden_overlap:{first}:{second}")


def _overlap_ratio(first: dict[str, Any], second: dict[str, Any]) -> float:
    left = max(float(first.get("x", 0)), float(second.get("x", 0)))
    top = max(float(first.get("y", 0)), float(second.get("y", 0)))
    right = min(float(first.get("x", 0)) + float(first.get("w", 0)), float(second.get("x", 0)) + float(second.get("w", 0)))
    bottom = min(float(first.get("y", 0)) + float(first.get("h", 0)), float(second.get("y", 0)) + float(second.get("h", 0)))
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    smallest = min(
        float(first.get("w", 0)) * float(first.get("h", 0)),
        float(second.get("w", 0)) * float(second.get("h", 0)),
    )
    return intersection / max(1.0, smallest)


def _validate_material_binding(errors: list[str], role: str, props: dict[str, Any], plan: LayoutPlan) -> None:
    expected = plan.materials.get(role)
    if expected is None:
        errors.append(f"unexpected_material_role:{role}")
        return
    if str(props.get("material_id") or "") != expected.material_id:
        errors.append(f"material_id_mismatch:{role}")
    if str(props.get("url") or "") != expected.file_url:
        errors.append(f"material_url_mismatch:{role}")
    parsed = urlparse(str(props.get("url") or ""))
    if parsed.scheme not in {"http", "https"} and not str(props.get("url") or "").startswith("/"):
        errors.append(f"material_url_not_allowed:{role}")


def _validate_bounds(errors: list[str], props: dict[str, Any], page_width: float, page_height: float) -> None:
    if not any(key in props for key in ("x", "y", "w", "h")):
        return
    x = _number(props.get("x"))
    y = _number(props.get("y"))
    width = _number(props.get("w"))
    height = _number(props.get("h"))
    if None in {x, y, width, height}:
        errors.append("element_non_finite_bounds")
        return
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > page_width + 1 or y + height > page_height + 1:
        errors.append("element_out_of_bounds")


def _validate_visual_bbox(errors: list[str], props: dict[str, Any]) -> None:
    bbox = props.get("visualBBox")
    if bbox is None:
        return
    if not isinstance(bbox, dict):
        errors.append("invalid_visual_bbox")
        return
    values = [_number(bbox.get(key)) for key in ("x", "y", "w", "h")]
    if any(value is None for value in values):
        errors.append("invalid_visual_bbox")
        return
    x, y, width, height = values
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1.0001 or y + height > 1.0001:
        errors.append("invalid_visual_bbox")


def _element_by_type(elements: list[Any], element_type: str) -> dict[str, Any] | None:
    return next((item for item in elements if isinstance(item, dict) and item.get("type") == element_type), None)


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
