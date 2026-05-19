import copy
import json
import re


class LayoutRepairer:
    PAGE_W = 1080
    PAGE_H = 1920
    GAP = 24

    def repair(self, raw_json_str: str, validation_errors: list[str]) -> dict | None:
        """Attempt to repair a malformed layout JSON. Returns repaired dict or None if unrepairable."""
        layout = self._parse_json(raw_json_str)
        if layout is None:
            return None

        layout = self._fill_missing_fields(layout)
        layout = self._fix_z_indexes(layout)
        layout = self._clamp_coordinates(layout)
        layout = self._resolve_overlaps(layout)
        return layout

    def _parse_json(self, raw: str) -> dict | None:
        """Try multiple strategies to parse JSON."""
        strategies = [
            lambda s: json.loads(s),
            lambda s: json.loads(re.sub(r",\s*([}\]])", r"\1", s)),  # Remove trailing commas
            lambda s: json.loads(self._extract_json_block(s)),  # Extract from markdown code block
        ]
        for strategy in strategies:
            try:
                result = strategy(raw)
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, KeyError):
                continue
        return None

    def _extract_json_block(self, s: str) -> str:
        """Extract JSON from markdown ```json ... ``` blocks."""
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
        if match:
            return match.group(1).strip()
        # Try to find first { and last }
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            return s[start:end + 1]
        return s

    def _fill_missing_fields(self, layout: dict) -> dict:
        result = copy.deepcopy(layout)
        if "page" not in result or not isinstance(result["page"], dict):
            result["page"] = {}
        result["page"].setdefault("width", 1080)
        result["page"].setdefault("height", 1920)
        result["page"].setdefault("background", "#FAF6F0")

        if "style" not in result or not isinstance(result["style"], dict):
            result["style"] = {}
        result["style"].setdefault("theme", "healing")
        result["style"].setdefault("font", "handwriting")

        if "elements" not in result or not isinstance(result["elements"], list):
            result["elements"] = []

        for el in result["elements"]:
            if isinstance(el, dict):
                el.setdefault("z_index", 0)
                if "props" not in el:
                    el["props"] = {}

        return result

    def _fix_z_indexes(self, layout: dict) -> dict:
        """Ensure z_index values are valid integers and respect element type hierarchy."""
        z_ranges = {
            "image": (0, 9),
            "decoration": (10, 19),
            "sticker": (20, 29),
            "text": (30, 39),
            "date_tag": (40, 49),
            "mood_tag": (40, 49),
            "weather_tag": (40, 49),
        }
        result = copy.deepcopy(layout)
        for i, el in enumerate(result.get("elements", [])):
            if not isinstance(el, dict):
                continue
            el_type = el.get("type", "")
            current_z = el.get("z_index", 0)
            try:
                current_z = int(current_z)
            except (ValueError, TypeError):
                current_z = z_ranges.get(el_type, (0, 0))[0]

            valid_range = z_ranges.get(el_type, (0, 99))
            if current_z < valid_range[0] or current_z > valid_range[1]:
                el["z_index"] = valid_range[0]
            else:
                el["z_index"] = current_z

        # Deduplicate z_index values within same type
        seen_z = {}
        for el in result.get("elements", []):
            el_type = el.get("type", "")
            z = el["z_index"]
            key = f"{el_type}:{z}"
            if key in seen_z:
                el["z_index"] = z + 1
            seen_z[key] = True

        return result

    def _clamp_coordinates(self, layout: dict) -> dict:
        """Clamp element coordinates to valid page bounds."""
        result = copy.deepcopy(layout)
        page_w = result.get("page", {}).get("width", self.PAGE_W)
        page_h = result.get("page", {}).get("height", self.PAGE_H)

        for el in result.get("elements", []):
            props = el.get("props", {})
            x = self._coerce_number(props.get("x", 0), 0)
            y = self._coerce_number(props.get("y", 0), 0)
            w = self._coerce_number(props.get("w", page_w), page_w)
            h = self._coerce_number(props.get("h", page_h), page_h)

            x = max(0, min(x, page_w - 1))
            y = max(0, min(y, page_h - 1))
            w = max(1, min(w, page_w - x))
            h = max(1, min(h, page_h - y))

            props["x"] = x
            props["y"] = y
            if "w" in props or el.get("type") in {"image", "text", "sticker", "decoration"}:
                props["w"] = w
            if "h" in props or el.get("type") in {"image", "text", "sticker", "decoration"}:
                props["h"] = h

        return result

    def _resolve_overlaps(self, layout: dict) -> dict:
        result = copy.deepcopy(layout)
        page_w = result.get("page", {}).get("width", self.PAGE_W)
        page_h = result.get("page", {}).get("height", self.PAGE_H)

        placed: list[dict] = []
        elements = result.get("elements", [])
        ordered = list(enumerate(elements))
        ordered.sort(key=lambda item: (self._coerce_number(item[1].get("z_index", 0), 0), item[0]))

        for _, el in ordered:
            if not isinstance(el, dict):
                continue
            props = el.get("props", {})
            x, y, w, h = self._element_box(el, page_w, page_h)

            if self._find_collision((x, y, w, h), placed) is not None:
                x, y = self._find_free_position(x, y, w, h, placed, page_w, page_h)

            self._set_element_box(el, props, x, y, w, h)
            placed.append({"left": x, "top": y, "right": x + w, "bottom": y + h})

        return result

    def _find_collision(self, box: tuple[int, int, int, int], placed: list[dict]) -> dict | None:
        left, top, w, h = box
        right = left + w
        bottom = top + h
        for item in placed:
            if not (right <= item["left"] or left >= item["right"] or bottom <= item["top"] or top >= item["bottom"]):
                return item
        return None

    def _element_box(self, el: dict, page_w: int, page_h: int) -> tuple[int, int, int, int]:
        props = el.get("props", {})
        el_type = el.get("type", "")
        x = self._coerce_number(props.get("x", 0), 0)
        y = self._coerce_number(props.get("y", 0), 0)
        w_default, h_default = self._default_element_size(el)
        w = self._coerce_number(props.get("w", w_default), w_default)
        h = self._coerce_number(props.get("h", h_default), h_default)

        x = max(0, min(x, max(0, page_w - 1)))
        y = max(0, min(y, max(0, page_h - 1)))
        w = max(1, min(w, max(1, page_w - x)))
        h = max(1, min(h, max(1, page_h - y)))

        if el_type == "text":
            h = max(h, self._estimate_text_height(props))
        return x, y, w, h

    def _default_element_size(self, el: dict) -> tuple[int, int]:
        el_type = el.get("type", "")
        props = el.get("props", {})
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
            size = self._coerce_number(props.get("size", 42), 42)
            width = self._coerce_number(props.get("w", 760), 760)
            lines = max(1, (len(content) // max(1, max(10, width // max(1, size // 2)))) + 1)
            return min(width, self.PAGE_W - 80), max(72, int(lines * size * 1.6))
        return 160, 120

    def _estimate_text_height(self, props: dict) -> int:
        size = self._coerce_number(props.get("size", 42), 42)
        content = str(props.get("content", "") or "")
        width = self._coerce_number(props.get("w", 760), 760)
        chars_per_line = max(8, width // max(1, size // 2))
        lines = max(1, (len(content) // chars_per_line) + 1)
        return max(72, int(lines * size * 1.55))

    def _set_element_box(self, el: dict, props: dict, x: int, y: int, w: int, h: int) -> None:
        props["x"] = x
        props["y"] = y
        if el.get("type") in {"image", "text", "sticker", "decoration"} or "w" in props:
            props["w"] = w
        if el.get("type") in {"image", "text", "sticker", "decoration"} or "h" in props:
            props["h"] = h

    def _find_free_position(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        placed: list[dict],
        page_w: int,
        page_h: int,
    ) -> tuple[int, int]:
        candidates = [
            (0, self.GAP),
            (self.GAP, 0),
            (0, -self.GAP),
            (-self.GAP, 0),
            (self.GAP, self.GAP),
            (-self.GAP, self.GAP),
            (self.GAP * 2, self.GAP),
            (0, self.GAP * 2),
            (-self.GAP * 2, self.GAP),
            (self.GAP, -self.GAP * 2),
            (self.GAP * 2, self.GAP * 2),
        ]

        for dx, dy in candidates:
            nx = max(0, min(x + dx, max(0, page_w - w)))
            ny = max(0, min(y + dy, max(0, page_h - h)))
            if self._find_collision((nx, ny, w, h), placed) is None:
                return nx, ny

        # Last resort: slide downward in small steps, then keep within bounds.
        for shift in range(self.GAP, self.GAP * 12, self.GAP):
            ny = min(max(0, page_h - h), y + shift)
            if self._find_collision((x, ny, w, h), placed) is None:
                return x, ny

        return max(0, min(x, max(0, page_w - w))), max(0, min(y, max(0, page_h - h)))

    def _coerce_number(self, value, default: int) -> int:
        try:
            number = int(float(value))
        except (TypeError, ValueError):
            return default
        return number
