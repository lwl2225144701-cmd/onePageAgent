from __future__ import annotations

from typing import Any

from app.ai.layout.compiler import PAGE_HEIGHT, PAGE_WIDTH, compile_layout_template
from app.ai.layout.template_specs import TEMPLATE_SPECS, template_summary


LAYOUT_FEWSHOTS = TEMPLATE_SPECS


def content_length_bucket(content_text: str) -> str:
    length = len(str(content_text or "").strip())
    if length <= 28:
        return "short"
    if length >= 120:
        return "long"
    return "medium"


def build_layout_policy(
    *,
    content_text: str,
    title_hint: str,
    selected_materials: dict[str, Any],
    page_width: int = PAGE_WIDTH,
    page_height: int = PAGE_HEIGHT,
) -> dict[str, Any]:
    length_bucket = content_length_bucket(content_text)
    title_length = len(str(title_hint or "").strip())
    safe_inset = round(page_width * 0.067)
    return {
        "page": {"width": page_width, "height": page_height},
        "content_length": length_bucket,
        "safe_inset": safe_inset,
        "bottom_whitespace_min": round(page_height * (0.14 if length_bucket != "long" else 0.09)),
        "title": {
            "max_lines": 2,
            "suggested_size": 64 if title_length <= 12 else 56 if title_length <= 20 else 48,
            "allow_wrap": True,
        },
        "body": {
            "suggested_size": 42 if length_bucket == "short" else 38 if length_bucket == "medium" else 34,
            "line_height": 1.8,
            "must_preserve_content": True,
        },
        "background": {"max_opacity": 0.18, "require_background_safe": True},
        "focal_sticker": {
            "max_width": round(page_width * (0.34 if length_bucket == "short" else 0.30 if length_bucket == "medium" else 0.23)),
            "must_not_cover_body": True,
        },
        "available_roles": [role for role, value in selected_materials.items() if value],
    }


def select_layout_fewshots(
    *,
    content_text: str,
    semantic: dict[str, Any],
    style: dict[str, Any],
    selected_materials: dict[str, Any],
    fallback_mode: str,
    limit: int = 4,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scenes = _semantic_scenes(semantic)
    theme = str(style.get("theme") or "healing")
    length_bucket = content_length_bucket(content_text)
    roles = {role for role, value in selected_materials.items() if value}
    material_count = sum(len(value) if isinstance(value, list) else 1 for value in selected_materials.values() if value)
    target_density = "low" if fallback_mode == "neutral_minimal" or length_bucket == "long" or material_count <= 1 else "medium"
    candidates: list[dict[str, Any]] = []

    for spec in TEMPLATE_SPECS:
        required = set(spec.get("required_roles", []))
        if required and not required.issubset(roles):
            continue
        score = 0
        reasons: list[str] = []
        if scenes.intersection(spec.get("scenes", [])):
            score += 6
            reasons.append("scene")
        if theme in spec.get("themes", []):
            score += 3
            reasons.append("theme")
        if length_bucket in spec.get("content_lengths", []):
            score += 3
            reasons.append("content_length")
        if target_density == spec.get("density"):
            score += 2
            reasons.append("density")
        role_matches = roles.intersection(set(spec.get("required_roles", [])) | set(spec.get("optional_roles", [])))
        if role_matches:
            score += min(3, len(role_matches))
            reasons.append("material_roles")
        if fallback_mode in spec.get("fallback_modes", []):
            score += 8
            reasons.append("fallback_mode")
        if not score and spec["id"] == "neutral_minimal_record":
            score = 1
            reasons.append("safe_default")
        candidates.append({"id": spec["id"], "score": score, "reasons": reasons})

    candidates.sort(key=lambda item: (-item["score"], item["id"]))
    selected_ids = [item["id"] for item in candidates[: max(1, min(4, limit))]]
    selected = [template_summary(spec) for template_id in selected_ids for spec in TEMPLATE_SPECS if spec["id"] == template_id]
    return candidates, selected


def render_layout_fewshot(example: dict[str, Any], selected_materials: dict[str, Any] | None = None) -> dict[str, Any]:
    output = compile_layout_template(
        template_id=example["id"],
        title="被猫治愈的一天",
        body="今天猫猫一直趴在键盘上不让我工作，最后只好抱着它一起看电影。",
        mood={"label": "开心", "icon": "😊"},
        authoritative_context={
            "date_text": "2026.06.19 周五",
            "weather_text": "晴",
            "weather_icon": "☀️",
            "weather_icon_key": "sunny",
            "weather_success": True,
        },
        selected_materials=selected_materials or {},
        style={"theme": example.get("themes", ["healing"])[0]},
    )
    return {"id": example["id"], "metadata": template_summary(example), "output": output}


def selected_material_bundle(items: list[dict[str, Any]]) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "background": None,
        "focal_sticker": None,
        "supporting_stickers": [],
        "decorations": [],
        "frame": None,
        "tape": None,
    }
    for item in items:
        role = str(item.get("safe_role") or item.get("suggested_role") or item.get("material_type") or "")
        if role == "background" and bundle["background"] is None:
            bundle["background"] = item
        elif role == "focal_sticker" and bundle["focal_sticker"] is None:
            bundle["focal_sticker"] = item
        elif role == "supporting_sticker":
            bundle["supporting_stickers"].append(item)
        elif role == "frame" and bundle["frame"] is None:
            bundle["frame"] = item
        elif role == "tape" and bundle["tape"] is None:
            bundle["tape"] = item
        else:
            bundle["decorations"].append(item)
    return bundle


def _semantic_scenes(semantic: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    text_analysis = semantic.get("text_analysis", {}) if isinstance(semantic.get("text_analysis"), dict) else {}
    for source in (semantic, text_analysis):
        for key in ("scene", "sub_scene", "intent"):
            value = source.get(key)
            if isinstance(value, list):
                values.update(str(item) for item in value if item)
            elif value:
                values.add(str(value))
    values.update(str(item) for item in semantic.get("positive_tags", []) if item)
    return values
