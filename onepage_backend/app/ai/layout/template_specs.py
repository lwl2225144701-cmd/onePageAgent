from __future__ import annotations

from typing import Any


TEMPLATE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "healing_watermark_center_sticker",
        "layout_type": "watermark_center",
        "themes": ["healing", "warm", "cute"],
        "scenes": ["daily_life", "home", "pet", "nature", "weather"],
        "content_lengths": ["short", "medium"],
        "required_roles": ["background", "focal_sticker"],
        "optional_roles": ["tape", "decoration", "frame", "supporting_sticker"],
        "default_optional_slots": {
            "background": True,
            "focal_sticker": True,
            "tape": True,
            "supporting_sticker": False,
            "decoration": False,
            "frame": False,
        },
        "density": "medium",
        "composition": "左上事实标签、上方偏左标题、大幅低透明背景、中部主贴纸、中下正文、底部留白。",
        "page_style": {"background": "#FAF6F0", "ink": "#5C4A3A", "muted_ink": "#927F6B", "font": "handwriting"},
        "slots": {
            "date": {"x": 0.067, "y": 0.046, "w": 0.34, "h": 0.035, "size": 28, "z": 40},
            "mood": {"x": 0.067, "y": 0.087, "w": 0.19, "h": 0.04, "size": 30, "z": 40},
            "weather": {"x": 0.285, "y": 0.087, "w": 0.22, "h": 0.04, "size": 30, "z": 40},
            "title": {"x": 0.067, "y": 0.16, "w": 0.78, "h": 0.12, "size": 64, "z": 35},
            "background": {"x": 0.04, "y": 0.245, "w": 0.92, "h": 0.43, "opacity": 0.12, "z": 1},
            "frame": {"x": 0.025, "y": 0.02, "w": 0.95, "h": 0.92, "opacity": 0.68, "z": 8},
            "tape": {"x": 0.10, "y": 0.325, "w": 0.80, "h": 0.035, "opacity": 0.9, "z": 18},
            "focal_sticker": {"x": 0.34, "y": 0.355, "w": 0.32, "h": 0.20, "opacity": 1, "z": 22},
            "supporting_sticker": {"x": 0.70, "y": 0.40, "w": 0.18, "h": 0.12, "opacity": 0.94, "z": 23},
            "decoration": {"x": 0.74, "y": 0.53, "w": 0.15, "h": 0.08, "opacity": 0.84, "z": 24},
            "body": {"x": 0.067, "y": 0.64, "w": 0.866, "h": 0.20, "size": 38, "line_height": 1.8, "z": 35},
        },
    },
    {
        "id": "text_forward_long_form",
        "layout_type": "text_forward",
        "themes": ["healing", "minimal", "calm", "warm", "vintage"],
        "scenes": ["daily_life", "study", "work", "self_growth", "study_reflection"],
        "content_lengths": ["long"],
        "required_roles": [],
        "optional_roles": ["background", "tape", "decoration"],
        "default_optional_slots": {"background": True, "tape": False, "decoration": False},
        "density": "low",
        "composition": "标题与长正文优先，素材退居纸张氛围，正文舒展并保留底部留白。",
        "page_style": {"background": "#F7F3EE", "ink": "#55483C", "muted_ink": "#948576", "font": "serif"},
        "slots": {
            "date": {"x": 0.067, "y": 0.046, "w": 0.34, "h": 0.035, "size": 28, "z": 40},
            "mood": {"x": 0.067, "y": 0.087, "w": 0.19, "h": 0.04, "size": 30, "z": 40},
            "weather": {"x": 0.285, "y": 0.087, "w": 0.22, "h": 0.04, "size": 30, "z": 40},
            "title": {"x": 0.067, "y": 0.155, "w": 0.84, "h": 0.11, "size": 58, "z": 35},
            "background": {"x": 0.08, "y": 0.24, "w": 0.84, "h": 0.48, "opacity": 0.08, "z": 1},
            "tape": {"x": 0.10, "y": 0.285, "w": 0.72, "h": 0.028, "opacity": 0.76, "z": 18},
            "decoration": {"x": 0.77, "y": 0.18, "w": 0.13, "h": 0.07, "opacity": 0.72, "z": 18},
            "body": {"x": 0.067, "y": 0.31, "w": 0.866, "h": 0.50, "size": 34, "line_height": 1.85, "z": 35},
        },
    },
    {
        "id": "neutral_minimal_record",
        "layout_type": "neutral_minimal",
        "themes": ["healing", "minimal", "warm", "calm"],
        "scenes": ["food_review", "daily_life", "general_daily", "health_recovery"],
        "content_lengths": ["short", "medium", "long"],
        "required_roles": [],
        "optional_roles": ["background", "supporting_sticker", "tape", "decoration"],
        "default_optional_slots": {
            "background": True,
            "supporting_sticker": False,
            "tape": False,
            "decoration": False,
        },
        "density": "low",
        "fallback_modes": ["neutral_minimal"],
        "composition": "没有强相关素材时以标题正文为主体，最多一枚辅贴和两处低风险装饰。",
        "page_style": {"background": "#FAF6F0", "ink": "#5C4A3A", "muted_ink": "#9A8976", "font": "handwriting"},
        "slots": {
            "date": {"x": 0.067, "y": 0.046, "w": 0.34, "h": 0.035, "size": 28, "z": 40},
            "mood": {"x": 0.067, "y": 0.087, "w": 0.19, "h": 0.04, "size": 30, "z": 40},
            "weather": {"x": 0.285, "y": 0.087, "w": 0.22, "h": 0.04, "size": 30, "z": 40},
            "title": {"x": 0.067, "y": 0.165, "w": 0.82, "h": 0.12, "size": 62, "z": 35},
            "background": {"x": 0.10, "y": 0.25, "w": 0.80, "h": 0.42, "opacity": 0.07, "z": 1},
            "tape": {"x": 0.10, "y": 0.305, "w": 0.62, "h": 0.03, "opacity": 0.72, "z": 18},
            "supporting_sticker": {"x": 0.70, "y": 0.43, "w": 0.17, "h": 0.11, "opacity": 0.82, "z": 22},
            "decoration": {"x": 0.76, "y": 0.20, "w": 0.13, "h": 0.07, "opacity": 0.72, "z": 18},
            "body": {"x": 0.067, "y": 0.36, "w": 0.82, "h": 0.40, "size": 38, "line_height": 1.85, "z": 35},
        },
    },
    {
        "id": "short_note_with_corner_accent",
        "layout_type": "short_note",
        "themes": ["cute", "healing", "warm", "calm"],
        "scenes": ["daily_life", "home", "pet", "cafe", "travel", "food"],
        "content_lengths": ["short"],
        "required_roles": [],
        "optional_roles": ["focal_sticker", "supporting_sticker", "decoration", "tape"],
        "default_optional_slots": {
            "focal_sticker": True,
            "supporting_sticker": False,
            "decoration": False,
            "tape": True,
        },
        "density": "low",
        "composition": "短句与标题形成上中部节奏，贴纸居中偏下，小装饰靠边，底部大留白。",
        "page_style": {"background": "#FFF8F0", "ink": "#5C4A3A", "muted_ink": "#9A8976", "font": "handwriting"},
        "slots": {
            "date": {"x": 0.067, "y": 0.046, "w": 0.34, "h": 0.035, "size": 28, "z": 40},
            "mood": {"x": 0.067, "y": 0.087, "w": 0.19, "h": 0.04, "size": 30, "z": 40},
            "weather": {"x": 0.285, "y": 0.087, "w": 0.22, "h": 0.04, "size": 30, "z": 40},
            "title": {"x": 0.067, "y": 0.17, "w": 0.80, "h": 0.12, "size": 64, "z": 35},
            "tape": {"x": 0.12, "y": 0.31, "w": 0.62, "h": 0.03, "opacity": 0.82, "z": 18},
            "focal_sticker": {"x": 0.54, "y": 0.34, "w": 0.31, "h": 0.20, "opacity": 1, "z": 22},
            "supporting_sticker": {"x": 0.68, "y": 0.48, "w": 0.17, "h": 0.11, "opacity": 0.9, "z": 23},
            "decoration": {"x": 0.75, "y": 0.61, "w": 0.14, "h": 0.08, "opacity": 0.82, "z": 24},
            "body": {"x": 0.067, "y": 0.48, "w": 0.52, "h": 0.18, "size": 40, "line_height": 1.8, "z": 35},
        },
    },
)


def get_template_spec(template_id: str) -> dict[str, Any]:
    for spec in TEMPLATE_SPECS:
        if spec["id"] == template_id:
            return spec
    raise KeyError(f"Unknown layout template: {template_id}")


def template_summary(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        key: spec[key]
        for key in (
            "id",
            "layout_type",
            "themes",
            "scenes",
            "content_lengths",
            "required_roles",
            "optional_roles",
            "default_optional_slots",
            "density",
            "composition",
        )
        if key in spec
    }
