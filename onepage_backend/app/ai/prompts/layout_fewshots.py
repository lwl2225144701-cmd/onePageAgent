from __future__ import annotations

from copy import deepcopy
from typing import Any


PAGE_WIDTH = 1080
PAGE_HEIGHT = 1920


LAYOUT_FEWSHOTS: tuple[dict[str, Any], ...] = (
    {
        "id": "healing_watermark_center_sticker",
        "layout_type": "watermark_center",
        "themes": ["healing", "warm", "cute"],
        "scenes": ["daily_life", "home", "pet"],
        "content_lengths": ["short", "medium"],
        "required_roles": ["background", "focal_sticker"],
        "optional_roles": ["decoration", "tape", "frame"],
        "density": "medium",
        "input": {
            "content_text": "今天猫猫一直趴在键盘上不让我工作，最后只好抱着它一起看电影。虽然是很平凡的一天，但感觉被治愈了。",
            "title": "被猫治愈的一天",
            "date_text": "$authoritative_context.date_text",
            "mood": {"label": "开心", "icon": "😊"},
            "weather": {
                "label": "$authoritative_context.weather_text",
                "icon": "$authoritative_context.weather_icon",
            },
            "theme": "healing",
            "scene": ["daily_life", "home", "pet"],
            "content_length": "medium",
            "selected_materials": {
                "background": {"material_id": "$background.material_id", "url": "$background.file_url"},
                "focal_sticker": {"material_id": "$focal_sticker.material_id", "url": "$focal_sticker.file_url"},
                "supporting_stickers": [],
                "decorations": [{"material_id": "$decoration.material_id", "url": "$decoration.file_url"}],
                "frame": {"material_id": "$frame.material_id", "url": "$frame.file_url"},
            },
        },
        "composition": "暖白底、低透明度大背景、左上信息、上方偏左标题、中部主贴纸、中下部正文、底部明显留白。",
    },
    {
        "id": "text_forward_long_form",
        "layout_type": "text_forward",
        "themes": ["healing", "minimal", "calm", "warm"],
        "scenes": ["daily_life", "study", "work", "self_growth"],
        "content_lengths": ["long"],
        "required_roles": [],
        "optional_roles": ["background", "decoration", "tape"],
        "density": "low",
        "input": {
            "content_text": "较长正文来自当前用户输入，完整保留主要信息并在中下部舒展排版。",
            "title": "今天慢慢写下来",
            "date_text": "$authoritative_context.date_text",
            "mood": {"label": "$mood.label", "icon": "$mood.icon"},
            "weather": {"label": "$authoritative_context.weather_text", "icon": "$authoritative_context.weather_icon"},
            "theme": "minimal",
            "scene": ["daily_life"],
            "content_length": "long",
            "selected_materials": {"background": {}, "focal_sticker": {}, "supporting_stickers": [], "decorations": [], "frame": {}},
        },
        "composition": "长正文优先，缩小或省略主贴纸，减少装饰，正文区域扩大并保留底部留白。",
    },
    {
        "id": "neutral_minimal_record",
        "layout_type": "neutral_minimal",
        "themes": ["healing", "minimal", "warm"],
        "scenes": ["food_review", "daily_life", "general_daily"],
        "content_lengths": ["short", "medium", "long"],
        "required_roles": [],
        "optional_roles": ["background", "supporting_sticker", "decoration", "tape"],
        "density": "low",
        "fallback_modes": ["neutral_minimal"],
        "input": {
            "content_text": "当没有强相关素材时，正文与标题是页面主体，不为了丰富画面硬塞贴纸。",
            "title": "今天的一页",
            "date_text": "$authoritative_context.date_text",
            "mood": {"label": "$mood.label", "icon": "$mood.icon"},
            "weather": {"label": "$authoritative_context.weather_text", "icon": "$authoritative_context.weather_icon"},
            "theme": "healing",
            "scene": ["daily_life"],
            "content_length": "medium",
            "selected_materials": {"background": {}, "focal_sticker": {}, "supporting_stickers": [], "decorations": [], "frame": {}},
        },
        "composition": "纯色或低密度纸底，无主贴纸也成立；最多一枚辅助贴纸和两处小装饰。",
    },
    {
        "id": "short_note_with_corner_accent",
        "layout_type": "short_note",
        "themes": ["cute", "healing", "warm", "calm"],
        "scenes": ["daily_life", "home", "pet", "cafe", "travel"],
        "content_lengths": ["short"],
        "required_roles": [],
        "optional_roles": ["focal_sticker", "supporting_sticker", "decoration"],
        "density": "low",
        "input": {
            "content_text": "一句值得记住的小事。",
            "title": "今天的小确幸",
            "date_text": "$authoritative_context.date_text",
            "mood": {"label": "$mood.label", "icon": "$mood.icon"},
            "weather": {"label": "$authoritative_context.weather_text", "icon": "$authoritative_context.weather_icon"},
            "theme": "healing",
            "scene": ["daily_life"],
            "content_length": "short",
            "selected_materials": {
                "background": {},
                "focal_sticker": {"material_id": "$focal_sticker.material_id", "url": "$focal_sticker.file_url"},
                "supporting_stickers": [],
                "decorations": [{"material_id": "$decoration.material_id", "url": "$decoration.file_url"}],
                "frame": {},
            },
        },
        "composition": "短文本不拉成长段；主贴纸居中偏下，小装饰靠边，底部保持大面积留白。",
    },
)


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
    safe_inset = round(page_width * 0.07)
    bottom_whitespace = round(page_height * (0.14 if length_bucket != "long" else 0.09))
    focal_width_ratio = 0.34 if length_bucket == "short" else 0.30 if length_bucket == "medium" else 0.23
    title_size = 64 if title_length <= 12 else 56 if title_length <= 20 else 48
    body_size = 42 if length_bucket == "short" else 38 if length_bucket == "medium" else 34
    return {
        "page": {"width": page_width, "height": page_height},
        "content_length": length_bucket,
        "safe_inset": safe_inset,
        "bottom_whitespace_min": bottom_whitespace,
        "title": {"max_lines": 2, "suggested_size": title_size, "allow_wrap": True},
        "body": {
            "suggested_size": body_size,
            "line_height": 1.8,
            "must_preserve_content": True,
            "expand_before_truncate": True,
        },
        "background": {"max_opacity": 0.18, "require_background_safe": True},
        "focal_sticker": {
            "max_width": round(page_width * focal_width_ratio),
            "shrink_for_long_content": length_bucket == "long",
            "must_not_cover_body": True,
        },
        "decorations": {
            "max_count": 2 if length_bucket == "long" else 3,
            "keep_near_edges": True,
            "must_not_cover": ["title", "body", "date_tag", "mood_tag", "weather_tag", "focal_subject"],
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
    limit: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scenes = _semantic_scenes(semantic)
    theme = str(style.get("theme") or "healing")
    length_bucket = content_length_bucket(content_text)
    roles = {role for role, value in selected_materials.items() if value}
    material_count = sum(len(value) if isinstance(value, list) else 1 for value in selected_materials.values() if value)
    target_density = "low" if fallback_mode == "neutral_minimal" or length_bucket == "long" or material_count <= 1 else "medium"
    candidates: list[dict[str, Any]] = []

    for example in LAYOUT_FEWSHOTS:
        required = set(example.get("required_roles", []))
        if required and not required.issubset(roles):
            continue
        score = 0
        reasons: list[str] = []
        if scenes.intersection(example.get("scenes", [])):
            score += 6
            reasons.append("scene")
        if theme in example.get("themes", []):
            score += 3
            reasons.append("theme")
        if length_bucket in example.get("content_lengths", []):
            score += 3
            reasons.append("content_length")
        if target_density == example.get("density"):
            score += 2
            reasons.append("density")
        role_matches = roles.intersection(set(example.get("required_roles", [])) | set(example.get("optional_roles", [])))
        if role_matches:
            score += min(3, len(role_matches))
            reasons.append("material_roles")
        if fallback_mode in example.get("fallback_modes", []):
            score += 8
            reasons.append("fallback_mode")
        if not score and example["id"] == "neutral_minimal_record":
            score = 1
            reasons.append("safe_default")
        candidates.append({"id": example["id"], "score": score, "reasons": reasons})

    candidates.sort(key=lambda item: (-item["score"], item["id"]))
    selected_ids = {item["id"] for item in candidates[: max(2, min(4, limit))]}
    selected = [render_layout_fewshot(example) for example in LAYOUT_FEWSHOTS if example["id"] in selected_ids]
    selected.sort(key=lambda item: next(index for index, candidate in enumerate(candidates) if candidate["id"] == item["id"]))
    return candidates, selected


def render_layout_fewshot(example: dict[str, Any]) -> dict[str, Any]:
    page_width = PAGE_WIDTH
    page_height = PAGE_HEIGHT
    content = str(example["input"]["content_text"])
    title = str(example["input"]["title"])
    length_bucket = content_length_bucket(content)
    inset = round(page_width * 0.07)
    header_y = round(page_height * 0.055)
    tag_y = round(page_height * 0.10)
    title_y = round(page_height * 0.17)
    background_y = round(page_height * 0.25)
    body_y = round(page_height * (0.61 if length_bucket != "long" else 0.54))
    body_h = round(page_height * (0.22 if length_bucket != "long" else 0.32))
    title_size = 64 if len(title) <= 12 else 54
    elements: list[dict[str, Any]] = []
    selected = example["input"].get("selected_materials", {})

    background = selected.get("background")
    if background:
        elements.append(
            _material_element(
                "image",
                background,
                role="background",
                x=inset,
                y=background_y,
                w=page_width - inset * 2,
                h=round(page_height * 0.42),
                opacity=0.12,
                z_index=1,
            )
        )
    frame = selected.get("frame")
    if frame:
        elements.append(
            _material_element(
                "decoration",
                frame,
                role="frame",
                x=round(page_width * 0.025),
                y=round(page_height * 0.02),
                w=round(page_width * 0.95),
                h=round(page_height * 0.92),
                opacity=0.72,
                z_index=8,
            )
        )
    elements.extend(
        [
            {
                "type": "date_tag",
                "props": {"date": example["input"]["date_text"], "x": inset, "y": header_y, "size": 28, "color": "#9A8976"},
                "z_index": 40,
            },
            {
                "type": "mood_tag",
                "props": {
                    "mood": example["input"]["mood"]["label"],
                    "icon": example["input"]["mood"]["icon"],
                    "x": inset,
                    "y": tag_y,
                    "size": 30,
                },
                "z_index": 40,
            },
            {
                "type": "weather_tag",
                "props": {
                    "weather": example["input"]["weather"]["label"],
                    "icon": example["input"]["weather"]["icon"],
                    "x": round(page_width * 0.28),
                    "y": tag_y,
                    "size": 30,
                },
                "z_index": 40,
            },
            {
                "type": "text",
                "props": {
                    "role": "title",
                    "content": title,
                    "x": inset,
                    "y": title_y,
                    "w": round(page_width * 0.72),
                    "size": title_size,
                    "lineHeight": 1.35,
                    "color": "#5C4A3A",
                    "align": "left",
                },
                "z_index": 35,
            },
        ]
    )
    focal = selected.get("focal_sticker")
    if focal:
        focal_w = round(page_width * (0.32 if length_bucket != "long" else 0.23))
        elements.append(
            _material_element(
                "sticker",
                focal,
                role="focal_sticker",
                x=round((page_width - focal_w) / 2),
                y=round(page_height * 0.37),
                w=focal_w,
                h=focal_w,
                opacity=1,
                z_index=22,
            )
        )
    decorations = selected.get("decorations") or []
    if decorations:
        decoration = decorations[0]
        elements.append(
            _material_element(
                "decoration",
                decoration,
                role="decoration",
                x=round(page_width * 0.72),
                y=round(page_height * 0.51),
                w=round(page_width * 0.16),
                h=round(page_width * 0.10),
                opacity=0.86,
                z_index=24,
            )
        )
    elements.append(
        {
            "type": "text",
            "props": {
                "role": "body",
                "content": content,
                "x": inset,
                "y": body_y,
                "w": page_width - inset * 2,
                "h": body_h,
                "size": 38 if length_bucket != "long" else 34,
                "lineHeight": 1.8,
                "color": "#5C4A3A",
                "align": "left",
            },
            "z_index": 35,
        }
    )
    return {
        "id": example["id"],
        "metadata": {
            key: deepcopy(example.get(key))
            for key in ("layout_type", "themes", "scenes", "content_lengths", "required_roles", "density", "composition")
        },
        "input": deepcopy(example["input"]),
        "output": {
            "page": {"width": page_width, "height": page_height, "background": "#F7F3EE"},
            "elements": elements,
            "style": {"theme": example["input"]["theme"], "font": "handwriting"},
        },
    }


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


def _material_element(
    element_type: str,
    material: dict[str, Any],
    *,
    role: str,
    x: int,
    y: int,
    w: int,
    h: int,
    opacity: float,
    z_index: int,
) -> dict[str, Any]:
    return {
        "type": element_type,
        "props": {
            "material_id": material["material_id"],
            "url": material["url"],
            "role": role,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "opacity": opacity,
            "fit": "contain",
        },
        "z_index": z_index,
    }


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
