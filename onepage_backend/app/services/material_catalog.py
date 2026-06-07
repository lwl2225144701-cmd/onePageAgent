from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_MIME = "image/svg+xml"

STICKER_CATEGORIES = {"动物", "花草", "天气自然", "爱心星星", "人物场景", "小物件", "节日符号"}
BACKGROUND_CATEGORIES = {"纸张纹理", "网格线条", "牛皮纸", "水彩", "留白底", "森系", "海边", "雨天"}
DECORATION_CATEGORIES = {"边框", "标签", "丝带", "框架", "分隔线", "角标", "装饰花纹"}

OPENCLIPART_TYPE_MAP = {
    "background": "background",
    "border": "decoration",
    "corner": "decoration",
    "divider": "decoration",
    "ornament": "decoration",
    "ribbon": "decoration",
    "vintage": "decoration",
    "wreath": "decoration",
    "japanese": "decoration",
    "misc": "decoration",
    "animal": "sticker",
    "cute": "sticker",
    "flower": "sticker",
    "heart": "sticker",
    "insect": "sticker",
    "nature": "sticker",
    "star": "sticker",
    "sticker": "sticker",
    "weather": "sticker",
}

CLIPSAFARI_TYPE_MAP = {
    "arrow": "decoration",
    "border": "decoration",
    "circle": "decoration",
    "crown": "decoration",
    "frame": "decoration",
    "label": "decoration",
    "ribbon": "decoration",
    "decorative": "decoration",
    "ornament": "decoration",
    "vintage": "decoration",
    "cat": "sticker",
    "dog": "sticker",
    "cloud": "sticker",
    "tree": "sticker",
    "bird": "sticker",
    "flower": "sticker",
    "heart": "sticker",
    "star": "sticker",
    "rainbow": "sticker",
    "butterfly": "sticker",
}

STICKER_DIRECTORY_CATEGORY_MAP = {
    "animal": "动物",
    "bird": "动物",
    "butterfly": "动物",
    "insect": "动物",
    "cat": "动物",
    "dog": "动物",
    "flower": "花草",
    "tree": "花草",
    "nature": "天气自然",
    "weather": "天气自然",
    "cloud": "天气自然",
    "heart": "爱心星星",
    "star": "爱心星星",
    "rainbow": "爱心星星",
    "crown": "节日符号",
    "opendoodles": "人物场景",
    "cute": "小物件",
    "sticker": "小物件",
}

DECORATION_DIRECTORY_CATEGORY_MAP = {
    "border": "边框",
    "corner": "角标",
    "arrow": "角标",
    "divider": "分隔线",
    "frame": "框架",
    "label": "标签",
    "ribbon": "丝带",
    "circle": "装饰花纹",
    "crown": "装饰花纹",
    "ornament": "装饰花纹",
    "decorative": "装饰花纹",
    "vintage": "装饰花纹",
    "wreath": "装饰花纹",
    "japanese": "装饰花纹",
    "misc": "装饰花纹",
}

BACKGROUND_KEYWORD_CATEGORY_MAP = {
    "sea": "海边",
    "ocean": "海边",
    "beach": "海边",
    "blue": "海边",
    "rain": "雨天",
    "cloud": "雨天",
    "storm": "雨天",
    "grey": "雨天",
    "gray": "雨天",
    "paper": "纸张纹理",
    "texture": "纸张纹理",
    "grain": "纸张纹理",
    "grid": "网格线条",
    "line": "网格线条",
    "check": "网格线条",
    "dot": "网格线条",
    "kraft": "牛皮纸",
    "brown": "牛皮纸",
    "vintage": "牛皮纸",
    "watercolor": "水彩",
    "watercolour": "水彩",
    "wash": "水彩",
    "blank": "留白底",
    "plain": "留白底",
    "white": "留白底",
    "forest": "森系",
    "leaf": "森系",
    "botanical": "森系",
}

BACKGROUND_SAFE_CATEGORIES = {"纸张纹理", "牛皮纸", "水彩", "留白底", "网格线条"}
HIGH_DENSITY_KEYWORDS = {
    "pattern",
    "floral",
    "flower",
    "winding",
    "line",
    "busy",
    "ornament",
    "decorative",
    "mandala",
    "repeat",
    "wallpaper",
    "碎花",
    "花纹",
    "重复",
}
LOW_DENSITY_KEYWORDS = {
    "paper",
    "blank",
    "plain",
    "white",
    "cream",
    "kraft",
    "watercolor",
    "wash",
    "texture",
    "grain",
    "留白",
    "纸",
    "水彩",
}
SEMANTIC_BLOCKLIST_KEYWORDS = {
    "buddha",
    "佛",
    "boxing",
    "boxer",
    "拳击",
    "fighter",
    "weapon",
    "gun",
    "skull",
    "宗教",
}

STYLE_KEYWORDS = {
    "line": "线稿",
    "outline": "线稿",
    "doodle": "手绘",
    "draw": "手绘",
    "sketch": "手绘",
    "illustration": "插画",
    "scene": "插画",
    "ornament": "装饰",
    "decor": "装饰",
    "vintage": "复古",
    "cute": "可爱",
    "minimal": "极简",
    "simple": "极简",
}

EMOTION_KEYWORDS = {
    "happy": "开心",
    "smile": "开心",
    "healing": "治愈",
    "soft": "治愈",
    "calm": "平静",
    "quiet": "平静",
    "alone": "独处",
    "solo": "独处",
    "festival": "节日",
    "party": "节日",
    "celebration": "节日",
    "holiday": "节日",
    "love": "治愈",
    "loving": "治愈",
    "chill": "平静",
    "chilling": "平静",
}

SCENE_KEYWORDS = {
    "sea": "海边",
    "ocean": "海边",
    "beach": "海边",
    "rain": "雨天",
    "storm": "雨天",
    "coffee": "咖啡",
    "book": "阅读",
    "read": "阅读",
    "office": "工作",
    "work": "工作",
    "travel": "旅行",
    "trip": "旅行",
    "family": "家庭",
    "home": "家庭",
    "camp": "露营",
    "tent": "露营",
    "cook": "家庭",
    "cooking": "家庭",
    "eat": "家庭",
    "eating": "家庭",
    "shop": "旅行",
    "shopping": "旅行",
    "study": "阅读",
    "typing": "工作",
    "paint": "创作",
    "painting": "创作",
    "garden": "森系",
    "gardening": "森系",
    "dance": "节日",
    "dancing": "节日",
    "ballet": "节日",
}


def infer_material_type(provider: str, directory_name: str) -> str:
    if provider == "opendoodles":
        return "sticker"
    if provider == "clipsafari":
        return CLIPSAFARI_TYPE_MAP.get(directory_name, "decoration")
    return OPENCLIPART_TYPE_MAP.get(directory_name, "sticker")


def extract_svg_metadata(file_path: Path) -> dict[str, str]:
    try:
        root = ET.parse(file_path).getroot()
    except ET.ParseError:
        return {}

    metadata: dict[str, str] = {}
    title = _first_text(root, ".//{http://www.w3.org/2000/svg}title") or _first_text(root, ".//title")
    desc = _first_text(root, ".//{http://www.w3.org/2000/svg}desc") or _first_text(root, ".//desc")
    if title:
        metadata["title"] = title.strip()
    if desc:
        metadata["desc"] = desc.strip()

    for attr_name in ("{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}docname", "id"):
        attr_value = root.attrib.get(attr_name)
        if attr_value:
            metadata[attr_name.rsplit('}', 1)[-1]] = attr_value.strip()
    dimensions = extract_svg_dimensions_from_root(root)
    if dimensions:
        width, height = dimensions
        metadata["asset_width"] = str(width)
        metadata["asset_height"] = str(height)
        metadata["aspect_ratio"] = f"{width / height:.6f}"
    return metadata


def extract_svg_dimensions_from_root(root: ET.Element) -> tuple[float, float] | None:
    view_box = root.attrib.get("viewBox") or root.attrib.get("viewbox")
    if view_box:
        numbers = [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", view_box)]
        if len(numbers) == 4 and numbers[2] > 0 and numbers[3] > 0:
            return numbers[2], numbers[3]

    width = _parse_svg_length(root.attrib.get("width"))
    height = _parse_svg_length(root.attrib.get("height"))
    if width and height:
        return width, height
    return None


def extract_svg_dimensions(svg_bytes: bytes) -> tuple[float, float] | None:
    try:
        root = ET.fromstring(svg_bytes)
    except ET.ParseError:
        return None
    return extract_svg_dimensions_from_root(root)


def build_builtin_material_record(*, root_dir: Path, file_path: Path) -> dict:
    relative_path = file_path.relative_to(root_dir).as_posix()
    parts = relative_path.split("/")
    provider = parts[0] if parts else "builtin"
    directory_name = parts[1] if len(parts) > 1 else provider
    metadata = extract_svg_metadata(file_path) if file_path.suffix.lower() == ".svg" else {}
    keywords = _extract_keywords(metadata, relative_path)
    material_type = infer_material_type(provider, directory_name)
    category = infer_category(
        material_type=material_type,
        directory_name=directory_name,
        keywords=keywords,
        provider=provider,
    )
    tags = infer_tags(provider=provider, directory_name=directory_name, keywords=keywords, category=category)
    style_tags, emotion_tags, scene_tags = derive_builtin_tags(
        material_type=material_type,
        directory_name=directory_name,
        category=category,
        tags=tags,
        keywords=keywords,
        provider=provider,
    )
    quality = infer_quality_profile(
        material_type=material_type,
        category=category,
        provider=provider,
        directory_name=directory_name,
        keywords=keywords,
    )
    display_name = infer_display_name(file_path=file_path, metadata=metadata)
    return {
        "provider": provider,
        "origin_path": relative_path,
        "display_name": display_name,
        "material_type": material_type,
        "category": category,
        "tags": tags,
        "style_tags": style_tags,
        "emotion_tags": emotion_tags,
        "scene_tags": scene_tags,
        "mime_type": SVG_MIME if file_path.suffix.lower() == ".svg" else "application/octet-stream",
        "metadata": metadata,
        "asset_width": _coerce_float(metadata.get("asset_width")),
        "asset_height": _coerce_float(metadata.get("asset_height")),
        "aspect_ratio": _coerce_float(metadata.get("aspect_ratio")),
        **quality,
    }


def infer_display_name(*, file_path: Path, metadata: dict[str, str]) -> str:
    for key in ("title", "docname"):
        value = metadata.get(key)
        if value:
            return _normalize_display_name(value)
    return _normalize_display_name(file_path.stem)


def infer_category(*, material_type: str, directory_name: str, keywords: list[str], provider: str | None = None) -> str:
    lowered_keywords = [keyword.lower() for keyword in keywords]
    if material_type == "background":
        for keyword in lowered_keywords:
            for token, category in BACKGROUND_KEYWORD_CATEGORY_MAP.items():
                if token in keyword:
                    return category
        return "纸张纹理"
    if material_type == "decoration":
        return DECORATION_DIRECTORY_CATEGORY_MAP.get(directory_name, "装饰花纹")
    if provider == "opendoodles" or directory_name == "opendoodles":
        return "人物场景"
    return STICKER_DIRECTORY_CATEGORY_MAP.get(directory_name, "小物件")


def infer_tags(*, provider: str, directory_name: str, keywords: list[str], category: str) -> list[str]:
    tags: list[str] = [category]
    if directory_name not in {provider, category}:
        tags.append(directory_name)
    if provider == "opendoodles":
        tags.extend(["scene", "illustration", "人物场景"])
    for keyword in keywords:
        candidate = keyword.strip()
        if not candidate:
            continue
        if candidate not in tags:
            tags.append(candidate)
    return tags[:12]


def derive_builtin_tags(
    *,
    material_type: str,
    directory_name: str,
    category: str,
    tags: list[str],
    keywords: list[str],
    provider: str,
) -> tuple[list[str], list[str], list[str]]:
    normalized_keywords = [item.lower() for item in [directory_name, category, *tags, *keywords]]

    style_tags: list[str] = []
    emotion_tags: list[str] = []
    scene_tags: list[str] = []

    for keyword in normalized_keywords:
        for token, style_value in STYLE_KEYWORDS.items():
            if token in keyword and style_value not in style_tags:
                style_tags.append(style_value)
        for token, emotion_value in EMOTION_KEYWORDS.items():
            if token in keyword and emotion_value not in emotion_tags:
                emotion_tags.append(emotion_value)
        for token, scene_value in SCENE_KEYWORDS.items():
            if token in keyword and scene_value not in scene_tags:
                scene_tags.append(scene_value)

    if material_type == "background" and category in BACKGROUND_CATEGORIES and category not in scene_tags:
        scene_tags.insert(0, category)
    if material_type == "decoration":
        if "装饰" not in style_tags:
            style_tags.insert(0, "装饰")
        if category == "装饰花纹" and "复古" not in style_tags and any("vintage" in item for item in normalized_keywords):
            style_tags.append("复古")
    if material_type == "sticker":
        if category == "人物场景" and "插画" not in style_tags:
            style_tags.insert(0, "插画")
        if category in {"爱心星星", "节日符号"} and "可爱" not in style_tags:
            style_tags.append("可爱")
        if provider == "opendoodles":
            if "治愈" not in emotion_tags:
                emotion_tags.append("治愈")
            if "平静" not in emotion_tags:
                emotion_tags.append("平静")

    return _dedupe(style_tags), _dedupe(emotion_tags), _dedupe(scene_tags)


def infer_quality_profile(
    *,
    material_type: str,
    category: str,
    provider: str,
    directory_name: str,
    keywords: list[str],
) -> dict:
    haystack = " ".join([provider, directory_name, category, *keywords]).lower()
    density = "medium"
    complexity = "medium"
    importance = "supporting"
    visual_style = "illustration" if provider == "opendoodles" else "decorative"
    background_safe = False
    semantic_blocked = any(token in haystack for token in SEMANTIC_BLOCKLIST_KEYWORDS)

    if any(token in haystack for token in LOW_DENSITY_KEYWORDS):
        density = "low"
        complexity = "low"
    if any(token in haystack for token in HIGH_DENSITY_KEYWORDS):
        density = "high"
        complexity = "high"

    if material_type == "background":
        visual_style = "paper" if category in {"纸张纹理", "牛皮纸", "留白底"} else "texture"
        background_safe = category in BACKGROUND_SAFE_CATEGORIES and density != "high" and not semantic_blocked
        importance = "background" if background_safe else "background_candidate"
    elif material_type == "sticker":
        importance = "focal" if category in {"人物场景", "动物", "花草", "小物件"} else "supporting"
        visual_style = "lineart" if "line" in haystack or "outline" in haystack else visual_style
    elif material_type == "decoration":
        importance = "decorative"
        visual_style = "tape" if category == "丝带" else "frame" if category in {"边框", "框架"} else "ornament"

    return {
        "visual_style": visual_style,
        "complexity": complexity,
        "density": density,
        "importance": importance,
        "background_safe": background_safe,
        "semantic_blocked": semantic_blocked,
    }


def render_svg_preview(svg_bytes: bytes, fallback_text: str) -> bytes | None:
    try:
        import cairosvg  # type: ignore

        return cairosvg.svg2png(bytestring=svg_bytes, output_width=512, output_height=512)
    except Exception:
        return None


def render_placeholder_preview(label: str) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return _minimal_png_bytes()

    image = Image.new("RGBA", (512, 512), (250, 246, 240, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, 488, 488), radius=32, outline=(208, 190, 168, 255), width=4)
    title = label[:24] or "material"
    font = ImageFont.load_default()
    text_bbox = draw.multiline_textbbox((0, 0), title, font=font, spacing=6)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    draw.multiline_text(
        ((512 - text_width) / 2, (512 - text_height) / 2),
        title,
        fill=(92, 74, 58, 255),
        font=font,
        spacing=6,
        align="center",
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _first_text(root: ET.Element, path: str) -> str | None:
    node = root.find(path)
    if node is None or node.text is None:
        return None
    return node.text


def _normalize_display_name(value: str) -> str:
    text = re.sub(r"\.svg$", "", value, flags=re.IGNORECASE)
    text = re.sub(r"[_-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip() or "material"


def _parse_svg_length(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"\s*(\d+(?:\.\d+)?)", value)
    if not match:
        return None
    number = float(match.group(1))
    return number if number > 0 else None


def _coerce_float(value: str | None) -> float | None:
    try:
        number = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return number if number and number > 0 else None


def _extract_keywords(metadata: dict[str, str], relative_path: str) -> list[str]:
    raw = " ".join([*metadata.values(), relative_path])
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", raw)
    result: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in {"openclipart", "opendoodles", "svg", "layer"}:
            continue
        if lowered not in result:
            result.append(lowered)
    return result[:16]


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _minimal_png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        b"\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0cIDATx\x9cc`\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\xdd\x9d\xb3"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
