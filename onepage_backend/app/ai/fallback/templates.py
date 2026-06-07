import copy

FALLBACK_TEMPLATES = {
    "happy": {
        "page": {"width": 1080, "height": 1920, "background": "#FFF8E7"},
        "elements": [
            {"type": "date_tag", "props": {"date": "", "font": "handwriting", "size": 28, "color": "#8B7D6B", "x": 80, "y": 100}, "z_index": 40},
            {"type": "mood_tag", "props": {"mood": "开心", "icon": "😊", "x": 80, "y": 150}, "z_index": 40},
            {"type": "text", "props": {"content": "今天真是美好的一天 ✨", "font": "handwriting", "size": 48, "color": "#5C4A3A", "x": 80, "y": 400, "w": 920, "align": "center", "lineHeight": 1.8}, "z_index": 30},
            {"type": "sticker", "props": {"url": "/materials/stickers/sunny_cat.png", "x": 400, "y": 700, "w": 280, "h": 280, "rotation": 0}, "z_index": 20},
        ],
        "style": {"theme": "warm", "font": "handwriting"},
    },
    "sad": {
        "page": {"width": 1080, "height": 1920, "background": "#F0F4F8"},
        "elements": [
            {"type": "date_tag", "props": {"date": "", "font": "handwriting", "size": 28, "color": "#8B7D6B", "x": 80, "y": 100}, "z_index": 40},
            {"type": "mood_tag", "props": {"mood": "安静", "icon": "🌧️", "x": 80, "y": 150}, "z_index": 40},
            {"type": "text", "props": {"content": "偶尔的雨天\n也是生活的一部分", "font": "handwriting", "size": 42, "color": "#6B7B8D", "x": 80, "y": 500, "w": 920, "align": "center", "lineHeight": 2.0}, "z_index": 30},
            {"type": "sticker", "props": {"url": "/materials/stickers/gentle_cloud.png", "x": 390, "y": 800, "w": 300, "h": 300, "rotation": 0}, "z_index": 20},
        ],
        "style": {"theme": "calm", "font": "handwriting"},
    },
    "excited": {
        "page": {"width": 1080, "height": 1920, "background": "#FFF0F5"},
        "elements": [
            {"type": "date_tag", "props": {"date": "", "font": "handwriting", "size": 28, "color": "#8B7D6B", "x": 80, "y": 100}, "z_index": 40},
            {"type": "mood_tag", "props": {"mood": "兴奋", "icon": "🎉", "x": 80, "y": 150}, "z_index": 40},
            {"type": "text", "props": {"content": "超棒的一天！\n记录下这份快乐 🎊", "font": "brush", "size": 52, "color": "#C97A8A", "x": 80, "y": 400, "w": 920, "align": "center", "lineHeight": 1.8}, "z_index": 30},
            {"type": "sticker", "props": {"url": "/materials/stickers/happy_star.png", "x": 415, "y": 750, "w": 250, "h": 250, "rotation": 0}, "z_index": 20},
            {"type": "decoration", "props": {"url": "/materials/decorations/washi_tape.png", "x": 40, "y": 350, "w": 1000, "h": 30, "rotation": -2}, "z_index": 10},
        ],
        "style": {"theme": "vivid", "font": "brush"},
    },
    "calm": {
        "page": {"width": 1080, "height": 1920, "background": "#F5F0E8"},
        "elements": [
            {"type": "date_tag", "props": {"date": "", "font": "handwriting", "size": 28, "color": "#8B7D6B", "x": 80, "y": 100}, "z_index": 40},
            {"type": "mood_tag", "props": {"mood": "平静", "icon": "🍃", "x": 80, "y": 150}, "z_index": 40},
            {"type": "text", "props": {"content": "静下心来\n感受此刻的美好", "font": "handwriting", "size": 42, "color": "#5C4A3A", "x": 80, "y": 500, "w": 920, "align": "center", "lineHeight": 2.0}, "z_index": 30},
            {"type": "sticker", "props": {"url": "/materials/stickers/botanical_line.png", "x": 440, "y": 800, "w": 200, "h": 200, "rotation": 0}, "z_index": 20},
        ],
        "style": {"theme": "healing", "font": "handwriting"},
    },
    "neutral": {
        "page": {"width": 1080, "height": 1920, "background": "#FAF6F0"},
        "elements": [
            {"type": "date_tag", "props": {"date": "", "font": "handwriting", "size": 28, "color": "#8B7D6B", "x": 80, "y": 100}, "z_index": 40},
            {"type": "mood_tag", "props": {"mood": "记录", "icon": "📝", "x": 80, "y": 150}, "z_index": 40},
            {"type": "text", "props": {"content": "记录今天的点滴\n平凡也值得珍藏", "font": "handwriting", "size": 42, "color": "#5C4A3A", "x": 80, "y": 500, "w": 920, "align": "center", "lineHeight": 2.0}, "z_index": 30},
            {"type": "decoration", "props": {"url": "/materials/decorations/line_divider.png", "x": 140, "y": 180, "w": 800, "h": 10}, "z_index": 10},
        ],
        "style": {"theme": "healing", "font": "handwriting"},
    },
    "nostalgic": {
        "page": {"width": 1080, "height": 1920, "background": "#F5EDDC"},
        "elements": [
            {"type": "date_tag", "props": {"date": "", "font": "handwriting", "size": 28, "color": "#8B7D6B", "x": 80, "y": 100}, "z_index": 40},
            {"type": "mood_tag", "props": {"mood": "怀旧", "icon": "📷", "x": 80, "y": 150}, "z_index": 40},
            {"type": "text", "props": {"content": "翻开记忆的相册\n那些珍贵的瞬间", "font": "serif", "size": 42, "color": "#5C4A3A", "x": 80, "y": 500, "w": 920, "align": "center", "lineHeight": 2.0}, "z_index": 30},
            {"type": "sticker", "props": {"url": "/materials/stickers/travel_ticket.png", "x": 380, "y": 800, "w": 320, "h": 320, "rotation": -5}, "z_index": 20},
            {"type": "decoration", "props": {"url": "/materials/tapes/vintage_tape.png", "x": 40, "y": 380, "w": 1000, "h": 40, "rotation": 1}, "z_index": 10},
        ],
        "style": {"theme": "vintage", "font": "serif"},
    },
}

DEFAULT_TEMPLATE = FALLBACK_TEMPLATES["neutral"]


def get_fallback_layout(emotion: str | None = None, content_text: str | None = None, page_date: str | None = None) -> dict:
    template = FALLBACK_TEMPLATES.get(emotion or "", DEFAULT_TEMPLATE)
    layout = copy.deepcopy(template)

    if page_date:
        for element in layout.get("elements", []):
            if element.get("type") == "date_tag":
                element.setdefault("props", {})["date"] = page_date

    if content_text:
        text_elements = [el for el in layout.get("elements", []) if el.get("type") == "text"]
        if text_elements:
            text_elements[0].setdefault("props", {})["content"] = content_text
        else:
            layout.setdefault("elements", []).append(
                {
                    "type": "text",
                    "props": {
                        "content": content_text,
                        "font": layout.get("style", {}).get("font", "handwriting"),
                        "size": 42,
                        "color": "#5C4A3A",
                        "x": 80,
                        "y": 500,
                        "w": 920,
                        "align": "left",
                        "lineHeight": 1.8,
                    },
                    "z_index": 30,
                }
            )

    return layout
