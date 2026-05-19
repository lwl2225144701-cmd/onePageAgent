REQUIRED_TOP_KEYS = {"page", "elements", "style"}
REQUIRED_PAGE_KEYS = {"width", "height", "background"}
REQUIRED_STYLE_KEYS = {"theme", "font"}
VALID_ELEMENT_TYPES = {"image", "text", "sticker", "decoration", "date_tag", "mood_tag", "weather_tag"}
VALID_THEMES = {"healing", "warm", "vintage", "minimal", "cute", "cool", "elegant", "vivid", "calm"}
VALID_FONTS = {"handwriting", "serif", "sans-serif", "brush"}


class LayoutValidator:
    def validate(self, layout: dict) -> list[str]:
        errors = []

        if not isinstance(layout, dict):
            return ["Layout must be a JSON object"]

        missing_keys = REQUIRED_TOP_KEYS - set(layout.keys())
        if missing_keys:
            errors.append(f"Missing top-level keys: {missing_keys}")

        if "page" in layout:
            errors.extend(self._validate_page(layout["page"]))

        if "elements" in layout:
            errors.extend(self._validate_elements(layout["elements"]))

        if "style" in layout:
            errors.extend(self._validate_style(layout["style"]))

        return errors

    def _validate_page(self, page: dict) -> list[str]:
        errors = []
        if not isinstance(page, dict):
            return ["'page' must be an object"]

        for key in REQUIRED_PAGE_KEYS:
            if key not in page:
                errors.append(f"page.{key} is required")

        w = page.get("width", 0)
        h = page.get("height", 0)
        if w and (w < 320 or w > 4096):
            errors.append(f"page.width {w} out of range (320-4096)")
        if h and (h < 320 or h > 4096):
            errors.append(f"page.height {h} out of range (320-4096)")

        return errors

    def _validate_elements(self, elements: list) -> list[str]:
        errors = []
        if not isinstance(elements, list):
            return ["'elements' must be an array"]

        for i, el in enumerate(elements):
            if not isinstance(el, dict):
                errors.append(f"elements[{i}] must be an object")
                continue
            el_type = el.get("type", "")
            if el_type not in VALID_ELEMENT_TYPES:
                errors.append(f"elements[{i}].type '{el_type}' is invalid")
            if "props" not in el:
                errors.append(f"elements[{i}].props is required")
            if "z_index" not in el:
                errors.append(f"elements[{i}].z_index is required")
            errors.extend(self._validate_coordinates(i, el))

        errors.extend(self._validate_overlaps(elements))
        return errors

    def _validate_coordinates(self, index: int, el: dict) -> list[str]:
        props = el.get("props")
        if not isinstance(props, dict):
            return [f"elements[{index}].props must be an object"]

        page_w = 1080
        page_h = 1920
        x = props.get("x")
        y = props.get("y")
        w = props.get("w")
        h = props.get("h")

        errors = []
        if x is not None:
            try:
                x_val = float(x)
                if x_val < 0 or x_val > page_w:
                    errors.append(f"elements[{index}].props.x {x_val} out of range (0-{page_w})")
            except (TypeError, ValueError):
                errors.append(f"elements[{index}].props.x must be numeric")
        if y is not None:
            try:
                y_val = float(y)
                if y_val < 0 or y_val > page_h:
                    errors.append(f"elements[{index}].props.y {y_val} out of range (0-{page_h})")
            except (TypeError, ValueError):
                errors.append(f"elements[{index}].props.y must be numeric")
        if w is not None:
            try:
                w_val = float(w)
                if w_val <= 0 or w_val > page_w:
                    errors.append(f"elements[{index}].props.w {w_val} out of range (1-{page_w})")
            except (TypeError, ValueError):
                errors.append(f"elements[{index}].props.w must be numeric")
        if h is not None:
            try:
                h_val = float(h)
                if h_val <= 0 or h_val > page_h:
                    errors.append(f"elements[{index}].props.h {h_val} out of range (1-{page_h})")
            except (TypeError, ValueError):
                errors.append(f"elements[{index}].props.h must be numeric")

        return errors

    def _validate_style(self, style: dict) -> list[str]:
        errors = []
        if not isinstance(style, dict):
            return ["'style' must be an object"]

        for key in REQUIRED_STYLE_KEYS:
            if key not in style:
                errors.append(f"style.{key} is required")

        if style.get("theme") and style["theme"] not in VALID_THEMES:
            errors.append(f"style.theme '{style['theme']}' is invalid")
        if style.get("font") and style["font"] not in VALID_FONTS:
            errors.append(f"style.font '{style['font']}' is invalid")

        return errors

    def _validate_overlaps(self, elements: list) -> list[str]:
        boxes = []
        for index, el in enumerate(elements):
            if not isinstance(el, dict):
                continue
            props = el.get("props", {})
            if not isinstance(props, dict):
                continue
            box = self._element_box(el)
            if box is None:
                continue
            left, top, right, bottom = box
            for prev_index, prev_box in boxes:
                if not (right <= prev_box[0] or left >= prev_box[2] or bottom <= prev_box[1] or top >= prev_box[3]):
                    return [f"elements[{index}] overlaps elements[{prev_index}]"]
            boxes.append((index, box))
        return []

    def _element_box(self, el: dict) -> tuple[float, float, float, float] | None:
        props = el.get("props", {})
        if not isinstance(props, dict):
            return None

        el_type = el.get("type", "")
        x = props.get("x")
        y = props.get("y")
        if x is None or y is None:
            return None

        try:
            x_val = float(x)
            y_val = float(y)
        except (TypeError, ValueError):
            return None

        w_default, h_default = self._default_size(el_type, props)
        try:
            w_val = float(props.get("w", w_default))
            h_val = float(props.get("h", h_default))
        except (TypeError, ValueError):
            return None

        return x_val, y_val, x_val + max(1.0, w_val), y_val + max(1.0, h_val)

    def _default_size(self, el_type: str, props: dict) -> tuple[int, int]:
        content = str(props.get("content", props.get("date", props.get("mood", props.get("weather", "")))) or "")
        if el_type == "image":
            return 320, 420
        if el_type == "sticker":
            return 180, 180
        if el_type == "decoration":
            return 240, 48
        if el_type == "date_tag":
            return 220, 48
        if el_type in {"mood_tag", "weather_tag"}:
            return max(120, min(260, 36 + len(content) * 18)), 48
        if el_type == "text":
            size = self._safe_int(props.get("size", 42), 42)
            width = self._safe_int(props.get("w", 760), 760)
            chars_per_line = max(8, width // max(1, size // 2))
            lines = max(1, (len(content) // chars_per_line) + 1)
            return min(width, 1080 - 80), max(72, int(lines * size * 1.55))
        return 160, 120

    def _safe_int(self, value, default: int) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default
