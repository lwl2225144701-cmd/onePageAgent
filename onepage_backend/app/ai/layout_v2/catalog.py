from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.ai.layout_v2.enums import MaterialRole


BASE_TAG_SLOTS = {
    "date": {
        "x": 18 / 266,
        "y": 22 / 472,
        "w": 0.34,
        "h": 0.035,
        "font_size": 28,
        "z_index": 40,
        "fill": None,
        "stroke": None,
        "color": "#7D6D5D",
        "padding_x": 0,
        "padding_y": 0,
        "border_radius": 0,
    },
    "mood": {
        "x": 18 / 266,
        "y": 42 / 472,
        "w": 0.19,
        "h": 0.045,
        "font_size": 30,
        "z_index": 40,
        "fill": "rgba(232,180,184,0.18)",
        "stroke": "rgba(232,180,184,0.40)",
        "stroke_width": 2,
        "color": "#BF6F81",
        "padding_x": 18,
        "padding_y": 8,
        "icon_gap": 8,
        "border_radius": 28,
    },
    "weather": {
        "x": 0.278,
        "y": 42 / 472,
        "w": 0.22,
        "h": 0.045,
        "font_size": 30,
        "z_index": 40,
        "fill": "rgba(74,124,139,0.12)",
        "stroke": "rgba(74,124,139,0.28)",
        "stroke_width": 2,
        "color": "#4F7C8B",
        "padding_x": 18,
        "padding_y": 8,
        "icon_gap": 8,
        "border_radius": 28,
    },
}

BASE_TEXT_SLOTS = {
    "title": {
        "x": 18 / 266,
        "y": 84 / 472,
        "w": 230 / 266,
        "h": 0.12,
        "font_size": 64,
        "line_height": 1.4,
        "max_lines": 2,
        "align": "left",
        "z_index": 35,
        "shadow": {"color": "#FFFAF2", "blur": 4, "opacity": 0.32, "offset_x": 0, "offset_y": 0},
    },
    "body": {
        "x": 18 / 266,
        "y": 300 / 472,
        "w": 230 / 266,
        "h": 0.23,
        "font_size": 42,
        "line_height": 1.9,
        "max_lines": 8,
        "align": "left",
        "z_index": 35,
        "shadow": {"color": "#FFFAF2", "blur": 3, "opacity": 0.22, "offset_x": 0, "offset_y": 0},
    },
}


def _asset_slot(
    role: MaterialRole,
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    opacity: float = 1.0,
    fit: str = "contain",
    z_index: int,
    rotation: float = 0.0,
    corner_radius: int = 24,
) -> dict[str, Any]:
    return {
        "role": role.value,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "opacity": opacity,
        "fit": fit,
        "object_position": "center",
        "z_index": z_index,
        "rotation": rotation,
        "corner_radius": corner_radius,
    }


def _template(
    *,
    template_id: str,
    layout_type: str,
    themes: list[str],
    scenes: list[str],
    lengths: list[str],
    roles: list[MaterialRole],
    fallback: str | None,
    page_background: str,
    font: str,
    asset_slots: dict[str, dict[str, Any]],
    body_slot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slots = deepcopy(BASE_TAG_SLOTS | BASE_TEXT_SLOTS)
    if body_slot:
        slots["body"].update(body_slot)
    slots.update(deepcopy(asset_slots))
    return {
        "id": template_id,
        "layout_type": layout_type,
        "themes": themes,
        "scenes": scenes,
        "content_lengths": lengths,
        "required_roles": [role.value for role in roles],
        "fallback_template": fallback,
        "density": "low" if layout_type in {"text_forward", "minimal_text"} else "medium",
        "page": {"width": 1080, "height": 1920, "background": page_background},
        "page_style": {
            "ink": "#5C4A3A",
            "muted_ink": "#8E7D6A",
            "font": font,
            "border": "#E5D8C7",
            "border_width": 3,
            "border_inset": 24,
            "border_radius": 28,
        },
        "slots": slots,
        "render_rules": {
            "bottom_whitespace_start": 0.84,
            "allowed_overlaps": [["tape", "focal_sticker"], ["background", "body"], ["background", "title"]],
            "forbidden_overlaps": [["title", "body"], ["focal_sticker", "body"], ["frame", "date"]],
        },
    }


TEMPLATE_CATALOG: tuple[dict[str, Any], ...] = (
    _template(
        template_id="watermark_center_tape",
        layout_type="watermark_center",
        themes=["healing", "warm", "cute"],
        scenes=["daily_life", "home", "pet", "food", "music", "work", "nature"],
        lengths=["short", "medium"],
        roles=[MaterialRole.BACKGROUND, MaterialRole.FOCAL_STICKER, MaterialRole.TAPE],
        fallback="watermark_center_clean",
        page_background="#FAF6F0",
        font="handwriting",
        asset_slots={
            "background": _asset_slot(MaterialRole.BACKGROUND, x=0, y=0, w=1, h=1, opacity=0.09, fit="watermark", z_index=1, corner_radius=0),
            "tape": _asset_slot(MaterialRole.TAPE, x=12 / 266, y=150 / 472, w=242 / 266, h=9 / 472, z_index=18, rotation=-1, corner_radius=8),
            "focal_sticker": _asset_slot(MaterialRole.FOCAL_STICKER, x=73 / 266, y=152 / 472, w=120 / 266, h=120 / 472, z_index=22),
        },
    ),
    _template(
        template_id="watermark_center_clean",
        layout_type="watermark_center",
        themes=["healing", "warm", "cute", "calm"],
        scenes=["daily_life", "home", "pet", "food", "music", "work", "nature"],
        lengths=["short", "medium"],
        roles=[MaterialRole.BACKGROUND, MaterialRole.FOCAL_STICKER],
        fallback="short_note_focal_center",
        page_background="#FAF6F0",
        font="handwriting",
        asset_slots={
            "background": _asset_slot(MaterialRole.BACKGROUND, x=0, y=0, w=1, h=1, opacity=0.09, fit="watermark", z_index=1, corner_radius=0),
            "focal_sticker": _asset_slot(MaterialRole.FOCAL_STICKER, x=73 / 266, y=152 / 472, w=120 / 266, h=120 / 472, z_index=22),
        },
    ),
    _template(
        template_id="watermark_center_frame",
        layout_type="watermark_center",
        themes=["cute", "warm", "vintage"],
        scenes=["pet", "food", "travel", "seasonal", "daily_life"],
        lengths=["short", "medium"],
        roles=[MaterialRole.BACKGROUND, MaterialRole.FOCAL_STICKER, MaterialRole.FRAME],
        fallback="watermark_center_clean",
        page_background="#FFF8F0",
        font="handwriting",
        asset_slots={
            "background": _asset_slot(MaterialRole.BACKGROUND, x=0, y=0, w=1, h=1, opacity=0.09, fit="watermark", z_index=1, corner_radius=0),
            "frame": _asset_slot(MaterialRole.FRAME, x=0.025, y=0.02, w=0.95, h=0.92, opacity=0.72, fit="fill", z_index=8, corner_radius=18),
            "focal_sticker": _asset_slot(MaterialRole.FOCAL_STICKER, x=73 / 266, y=152 / 472, w=120 / 266, h=120 / 472, z_index=22),
        },
    ),
    _template(
        template_id="watermark_left_focal",
        layout_type="watermark_left",
        themes=["calm", "minimal", "warm", "vintage"],
        scenes=["reading", "exercise", "music", "outing", "daily_life", "travel"],
        lengths=["short", "medium"],
        roles=[MaterialRole.BACKGROUND, MaterialRole.FOCAL_STICKER],
        fallback="short_note_focal_center",
        page_background="#F5F0E8",
        font="serif",
        asset_slots={
            "background": _asset_slot(MaterialRole.BACKGROUND, x=0, y=0, w=1, h=168 / 472, opacity=0.16, fit="cover", z_index=1, corner_radius=0),
            "focal_sticker": _asset_slot(MaterialRole.FOCAL_STICKER, x=16 / 266, y=152 / 472, w=120 / 266, h=120 / 472, z_index=22),
        },
    ),
    _template(
        template_id="watermark_right_focal",
        layout_type="watermark_right",
        themes=["calm", "minimal", "warm", "vivid"],
        scenes=["study", "shopping", "travel", "daily_life", "home", "outing"],
        lengths=["short", "medium"],
        roles=[MaterialRole.BACKGROUND, MaterialRole.FOCAL_STICKER],
        fallback="short_note_focal_right",
        page_background="#F5F0E8",
        font="serif",
        asset_slots={
            "background": _asset_slot(MaterialRole.BACKGROUND, x=0, y=0, w=1, h=168 / 472, opacity=0.16, fit="cover", z_index=1, corner_radius=0),
            "focal_sticker": _asset_slot(MaterialRole.FOCAL_STICKER, x=130 / 266, y=152 / 472, w=120 / 266, h=120 / 472, z_index=22),
        },
    ),
    _template(
        template_id="short_note_focal_center",
        layout_type="short_note",
        themes=["healing", "warm", "cute", "calm"],
        scenes=["daily_life", "home", "pet", "food", "outing", "travel", "general_daily"],
        lengths=["short", "medium"],
        roles=[MaterialRole.FOCAL_STICKER],
        fallback="minimal_text_only",
        page_background="#FFF8F0",
        font="handwriting",
        asset_slots={
            "focal_sticker": _asset_slot(MaterialRole.FOCAL_STICKER, x=73 / 266, y=152 / 472, w=120 / 266, h=120 / 472, z_index=22),
        },
    ),
    _template(
        template_id="short_note_focal_right",
        layout_type="short_note",
        themes=["healing", "warm", "cute", "calm"],
        scenes=["daily_life", "home", "pet", "food", "outing", "travel", "general_daily"],
        lengths=["short", "medium"],
        roles=[MaterialRole.FOCAL_STICKER],
        fallback="minimal_text_only",
        page_background="#FFF8F0",
        font="handwriting",
        asset_slots={
            "focal_sticker": _asset_slot(MaterialRole.FOCAL_STICKER, x=130 / 266, y=152 / 472, w=120 / 266, h=120 / 472, z_index=22),
        },
    ),
    _template(
        template_id="text_forward_background",
        layout_type="text_forward",
        themes=["minimal", "calm", "warm", "vintage", "healing"],
        scenes=["daily_life", "study", "work", "self_growth", "reading", "general_daily"],
        lengths=["long"],
        roles=[MaterialRole.BACKGROUND],
        fallback="text_forward_clean",
        page_background="#F7F3EE",
        font="serif",
        asset_slots={
            "background": _asset_slot(MaterialRole.BACKGROUND, x=0, y=0, w=1, h=0.54, opacity=0.07, fit="watermark", z_index=1, corner_radius=0),
        },
        body_slot={"y": 0.30, "h": 0.52, "font_size": 34, "line_height": 1.85, "max_lines": 18},
    ),
    _template(
        template_id="text_forward_clean",
        layout_type="text_forward",
        themes=["minimal", "calm", "warm", "vintage", "healing"],
        scenes=["daily_life", "study", "work", "self_growth", "reading", "general_daily"],
        lengths=["long"],
        roles=[],
        fallback="minimal_text_only",
        page_background="#F7F3EE",
        font="serif",
        asset_slots={},
        body_slot={"y": 0.30, "h": 0.52, "font_size": 34, "line_height": 1.85, "max_lines": 18},
    ),
    _template(
        template_id="minimal_text_only",
        layout_type="minimal_text",
        themes=["minimal", "calm", "healing", "warm", "cute", "vintage", "vivid"],
        scenes=["daily_life", "general_daily", "home", "pet", "food", "outing", "travel", "study", "work", "reading", "exercise", "self_growth"],
        lengths=["short", "medium", "long"],
        roles=[],
        fallback=None,
        page_background="#FAF6F0",
        font="handwriting",
        asset_slots={},
        body_slot={"y": 0.34, "h": 0.43, "font_size": 40, "line_height": 1.85, "max_lines": 14},
    ),
)


def get_template(template_id: str) -> dict[str, Any]:
    for template in TEMPLATE_CATALOG:
        if template["id"] == template_id:
            return deepcopy(template)
    raise KeyError(f"unknown_layout_v2_template:{template_id}")


def list_templates() -> list[dict[str, Any]]:
    return [deepcopy(template) for template in TEMPLATE_CATALOG]


def public_template_summary(template: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(template[key])
        for key in ("id", "layout_type", "themes", "scenes", "content_lengths", "required_roles", "fallback_template", "density")
    }
