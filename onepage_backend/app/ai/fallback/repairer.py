import copy
import json
import re


class LayoutRepairer:
    PAGE_W = 1080
    PAGE_H = 1920
    GAP = 24

    def repair(self, raw_json_str: str, validation_errors: list[str], asset_context: dict | None = None) -> dict | None:
        """Attempt to repair a malformed layout JSON. Returns repaired dict or None if unrepairable."""
        layout = self._parse_json(raw_json_str)
        if layout is None:
            return None

        layout = self._fill_missing_fields(layout)
        layout = self._fix_z_indexes(layout)
        layout = self._sanitize_asset_urls(layout, asset_context or {})
        layout = self._apply_background_preference(layout, asset_context or {})
        layout = self._swap_duplicate_assets(layout, asset_context or {})
        layout = self._ensure_minimum_material_elements(layout, asset_context or {})
        layout = self._preserve_asset_aspect_ratios(layout, asset_context or {})
        layout = self._rebalance_assets(layout, asset_context or {})
        layout = self._clamp_coordinates(layout)
        layout = self._resolve_overlaps(layout)
        layout = self._protect_text_readability(layout)
        return layout

    def repair_conservative(self, raw_json_str: str, asset_context: dict | None = None) -> dict | None:
        """Repair only schema, allowlist, z-index, and page-bound violations."""
        layout = self._parse_json(raw_json_str)
        if layout is None:
            return None
        layout = self._fill_missing_fields(layout)
        layout = self._fix_z_indexes(layout)
        layout = self._sanitize_asset_urls(layout, asset_context or {})
        return self._clamp_coordinates(layout)

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
            default_w, default_h = self._default_element_size(el)
            x = self._coerce_number(props.get("x", 0), 0)
            y = self._coerce_number(props.get("y", 0), 0)
            w = self._coerce_number(props.get("w", default_w), default_w)
            h = self._coerce_number(props.get("h", default_h), default_h)

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
        ordered.sort(key=lambda item: (self._placement_priority(item[1]), self._coerce_number(item[1].get("z_index", 0), 0), item[0]))

        for _, el in ordered:
            if not isinstance(el, dict):
                continue
            props = el.get("props", {})
            x, y, w, h = self._element_box(el, page_w, page_h)

            collision = self._find_collision((x, y, w, h), placed)
            if collision is not None:
                x, y, w, h = self._relayout_conflicting_element(el, x, y, w, h, placed, page_w, page_h)

            self._set_element_box(el, props, x, y, w, h)
            placed.append(
                {
                    "left": x,
                    "top": y,
                    "right": x + w,
                    "bottom": y + h,
                    "background": self._is_background_like(el, x, y, w, h),
                    "element_type": el.get("type"),
                }
            )

        return result

    def _find_collision(self, box: tuple[int, int, int, int], placed: list[dict]) -> dict | None:
        left, top, w, h = box
        right = left + w
        bottom = top + h
        for item in placed:
            if item.get("background"):
                continue
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
        explicit_lines = max(1, len(content.splitlines()))
        longest_line = max((len(line) for line in content.splitlines()), default=len(content))
        chars_per_line = max(8, width // max(12, size // 2))
        wrapped_lines = max(1, (longest_line // chars_per_line) + 1)
        lines = max(explicit_lines, wrapped_lines)
        return max(72, min(560, int(lines * size * 1.55)))

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

    def _sanitize_asset_urls(self, layout: dict, asset_context: dict) -> dict:
        result = copy.deepcopy(layout)
        candidate_groups = self._candidate_groups(asset_context)
        input_image_urls = asset_context.get("input_image_urls", []) if isinstance(asset_context, dict) else []
        by_type: dict[str, list[str]] = {"background": [], "sticker": [], "decoration": []}
        by_url: dict[str, dict] = {}

        for group in candidate_groups:
            material_type = group.get("material_type")
            if material_type not in by_type:
                continue
            for item in group.get("items", []):
                url = str(item.get("file_url") or "").strip()
                if url and url not in by_type[material_type]:
                    by_type[material_type].append(url)
                    by_url[url] = item

        allowed_image_urls = set(str(url).strip() for url in input_image_urls if str(url).strip())
        allowed_image_urls.update(by_type["background"])

        sanitized_elements = []
        for element in result.get("elements", []):
            if not isinstance(element, dict):
                continue
            element_type = element.get("type")
            props = element.get("props", {})
            url = str(props.get("url") or "").strip()

            if element_type == "image" and url:
                if url in allowed_image_urls:
                    self._bind_material_props(props, by_url.get(url), role="background" if url in by_type["background"] else "")
                    sanitized_elements.append(element)
                    continue
                replacement = by_type["background"][0] if by_type["background"] else (input_image_urls[0] if input_image_urls else "")
                if replacement:
                    props["url"] = replacement
                    self._bind_material_props(props, by_url.get(replacement))
                    sanitized_elements.append(element)
                continue

            if element_type in {"sticker", "decoration"} and url:
                candidates = by_type[element_type]
                if url in candidates:
                    self._bind_material_props(props, by_url.get(url))
                    sanitized_elements.append(element)
                    continue
                if candidates:
                    props["url"] = candidates[0]
                    self._bind_material_props(props, by_url.get(candidates[0]))
                    sanitized_elements.append(element)
                continue

            sanitized_elements.append(element)

        result["elements"] = sanitized_elements
        return result

    def _apply_background_preference(self, layout: dict, asset_context: dict) -> dict:
        result = copy.deepcopy(layout)
        groups = self._candidate_groups(asset_context)
        preferred = None
        for group in groups:
            if group.get("material_type") != "background":
                continue
            items = group.get("items", [])
            if items:
                preferred = items[0]
                break

        if preferred is None:
            return result

        image_elements = [el for el in result.get("elements", []) if isinstance(el, dict) and el.get("type") == "image"]
        if image_elements:
            image_elements[0].setdefault("props", {})
            image_elements[0]["props"]["url"] = preferred.get("file_url") or preferred.get("preview_url") or image_elements[0]["props"].get("url")
            self._bind_material_props(image_elements[0]["props"], preferred, role="background")
            page_w = result.get("page", {}).get("width", self.PAGE_W)
            page_h = result.get("page", {}).get("height", self.PAGE_H)
            inset = round(page_w * 0.07)
            image_elements[0]["props"]["x"] = inset
            image_elements[0]["props"]["y"] = round(page_h * 0.24)
            image_elements[0]["props"]["w"] = page_w - inset * 2
            image_elements[0]["props"]["h"] = round(page_h * 0.44)
            image_elements[0]["props"]["fit"] = "contain"
            image_elements[0]["props"]["opacity"] = min(self._coerce_float(image_elements[0]["props"].get("opacity"), 0.14), 0.18)
            image_elements[0]["z_index"] = 0
            return result

        result.setdefault("elements", []).insert(
            0,
            {
                "type": "image",
                "props": {
                    "material_id": preferred.get("material_id"),
                    "url": preferred.get("file_url") or preferred.get("preview_url"),
                    "role": "background",
                    "x": round(result.get("page", {}).get("width", self.PAGE_W) * 0.07),
                    "y": round(result.get("page", {}).get("height", self.PAGE_H) * 0.24),
                    "w": round(result.get("page", {}).get("width", self.PAGE_W) * 0.86),
                    "h": round(result.get("page", {}).get("height", self.PAGE_H) * 0.44),
                    "fit": "contain",
                    "opacity": 0.14,
                },
                "z_index": 0,
            },
        )
        return result

    def _ensure_minimum_material_elements(self, layout: dict, asset_context: dict) -> dict:
        result = copy.deepcopy(layout)
        candidates = self._asset_candidates_by_type(asset_context)
        fallback_mode = str(asset_context.get("fallback_mode") or "none") if isinstance(asset_context, dict) else "none"
        elements = result.setdefault("elements", [])
        used_urls = {
            str(element.get("props", {}).get("url") or "").strip()
            for element in elements
            if isinstance(element, dict) and isinstance(element.get("props"), dict)
        }
        used_urls.discard("")

        sticker_count = sum(1 for element in elements if isinstance(element, dict) and element.get("type") == "sticker")
        decoration_count = sum(1 for element in elements if isinstance(element, dict) and element.get("type") == "decoration")

        sticker_limit = 1 if fallback_mode == "neutral_minimal" else 3
        decoration_limit = 2 if fallback_mode == "neutral_minimal" else 2

        for candidate in self._rank_candidates(candidates.get("sticker", [])):
            if sticker_count >= sticker_limit:
                break
            role = str(candidate.get("safe_role") or candidate.get("suggested_role") or "")
            if fallback_mode == "neutral_minimal" and role == "focal_sticker":
                continue
            url = str(candidate.get("file_url") or "").strip()
            if not url or url in used_urls:
                continue
            elements.append(self._element_from_candidate(candidate, "sticker", sticker_count))
            used_urls.add(url)
            sticker_count += 1

        for candidate in self._rank_candidates(candidates.get("decoration", [])):
            if decoration_count >= decoration_limit:
                break
            url = str(candidate.get("file_url") or "").strip()
            if not url or url in used_urls:
                continue
            elements.append(self._element_from_candidate(candidate, "decoration", decoration_count))
            used_urls.add(url)
            decoration_count += 1

        return result

    def _preserve_asset_aspect_ratios(self, layout: dict, asset_context: dict) -> dict:
        result = copy.deepcopy(layout)
        ratio_by_url = self._asset_ratio_map(asset_context)
        page_w = result.get("page", {}).get("width", self.PAGE_W)
        page_h = result.get("page", {}).get("height", self.PAGE_H)

        for element in result.get("elements", []):
            if not isinstance(element, dict) or element.get("type") not in {"image", "sticker", "decoration"}:
                continue
            props = element.get("props", {})
            url = str(props.get("url") or "").strip()
            ratio = ratio_by_url.get(url)
            if not ratio:
                continue

            x = self._coerce_number(props.get("x", 0), 0)
            y = self._coerce_number(props.get("y", 0), 0)
            current_w = self._coerce_number(props.get("w", 0), 0)
            current_h = self._coerce_number(props.get("h", 0), 0)
            default_w, default_h = self._default_element_size(element)
            current_w = current_w or default_w
            current_h = current_h or default_h

            if element.get("type") == "image":
                max_w = max(1, page_w - x)
                max_h = max(1, page_h - y)
            else:
                max_w = min(360, max(1, page_w - x))
                max_h = min(360, max(1, page_h - y))

            next_w, next_h = self._fit_box_to_ratio(current_w, current_h, ratio, max_w, max_h)
            props["w"] = next_w
            props["h"] = next_h

        return result

    def _swap_duplicate_assets(self, layout: dict, asset_context: dict) -> dict:
        result = copy.deepcopy(layout)
        alternatives = self._asset_candidates_by_type(asset_context)
        used_per_type: dict[str, set[str]] = {"sticker": set(), "decoration": set(), "image": set()}

        for element in result.get("elements", []):
            if not isinstance(element, dict):
                continue
            element_type = element.get("type")
            if element_type not in {"sticker", "decoration", "image"}:
                continue
            props = element.get("props", {})
            current_url = str(props.get("url") or "").strip()
            candidate_type = "background" if element_type == "image" else element_type
            if not current_url:
                continue
            if current_url not in used_per_type[element_type]:
                used_per_type[element_type].add(current_url)
                continue
            for candidate in alternatives.get(candidate_type, []):
                candidate_url = str(candidate.get("file_url") or "").strip()
                if candidate_url and candidate_url not in used_per_type[element_type]:
                    props["url"] = candidate_url
                    self._bind_material_props(props, candidate)
                    used_per_type[element_type].add(candidate_url)
                    break

        return result

    def _rebalance_assets(self, layout: dict, asset_context: dict) -> dict:
        result = copy.deepcopy(layout)
        page_w = result.get("page", {}).get("width", self.PAGE_W)
        page_h = result.get("page", {}).get("height", self.PAGE_H)
        metadata_by_url = self._asset_metadata_map(asset_context)

        for element in result.get("elements", []):
            if not isinstance(element, dict):
                continue
            element_type = element.get("type")
            if element_type not in {"image", "sticker", "decoration"}:
                continue
            props = element.get("props", {})
            url = str(props.get("url") or "").strip()
            metadata = metadata_by_url.get(url, {})
            if metadata:
                self._apply_zone_hint(element, metadata, page_w, page_h)
                self._apply_size_hint(element, metadata, page_w, page_h)
                if metadata.get("suggested_z_index") is not None:
                    element["z_index"] = int(metadata["suggested_z_index"])

        return result

    def _asset_ratio_map(self, asset_context: dict) -> dict[str, float]:
        result: dict[str, float] = {}
        for group in self._candidate_groups(asset_context):
            for item in group.get("items", []):
                ratio = self._coerce_ratio(item.get("aspect_ratio"))
                if not ratio:
                    width = self._coerce_ratio(item.get("asset_width"))
                    height = self._coerce_ratio(item.get("asset_height"))
                    ratio = width / height if width and height else None
                if not ratio:
                    continue
                for key in ("file_url", "preview_url", "raw_file_url"):
                    url = str(item.get(key) or "").strip()
                    if url:
                        result[url] = ratio
        return result

    def _asset_candidates_by_type(self, asset_context: dict) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {"background": [], "sticker": [], "decoration": []}
        for group in self._candidate_groups(asset_context):
            material_type = str(group.get("material_type", "")).strip()
            if material_type in result:
                result[material_type] = [item for item in group.get("items", []) if isinstance(item, dict)]
        return result

    def _rank_candidates(self, candidates: list[dict]) -> list[dict]:
        def key(item: dict) -> tuple[int, int, int]:
            density = str(item.get("density") or "")
            importance = str(item.get("importance") or "")
            score = self._coerce_number(item.get("score", 0), 0)
            density_rank = {"low": 0, "medium": 1, "high": 3}.get(density, 1)
            importance_rank = {"focal": 0, "decorative": 0, "supporting": 1}.get(importance, 1)
            return density_rank, importance_rank, -score

        return sorted([item for item in candidates if isinstance(item, dict)], key=key)

    def _element_from_candidate(self, candidate: dict, element_type: str, index: int) -> dict:
        size_hint = str(candidate.get("suggested_size") or "")
        base_size = {"small": 140, "medium": 200, "large": 280}.get(size_hint, 180)
        zone = str(candidate.get("suggested_zone") or "")
        role = str(candidate.get("safe_role") or candidate.get("suggested_role") or element_type)
        if role == "frame":
            inset_x = round(self.PAGE_W * 0.025)
            inset_y = round(self.PAGE_H * 0.02)
            return {
                "type": "decoration",
                "props": {
                    "material_id": candidate.get("material_id"),
                    "url": candidate.get("file_url") or candidate.get("preview_url"),
                    "role": "frame",
                    "x": inset_x,
                    "y": inset_y,
                    "w": self.PAGE_W - inset_x * 2,
                    "h": round(self.PAGE_H * 0.92),
                    "opacity": 0.72,
                    "rotation": 0,
                },
                "z_index": 10,
            }
        if element_type == "decoration":
            base_size = 180 if size_hint == "small" else 260
        x, y = self._initial_position_for_zone(zone, element_type, index, base_size, base_size)
        return {
            "type": element_type,
            "props": {
                "material_id": candidate.get("material_id"),
                "url": candidate.get("file_url") or candidate.get("preview_url"),
                "role": role,
                "x": x,
                "y": y,
                "w": base_size,
                "h": base_size,
                "rotation": 0,
            },
            "z_index": self._coerce_number(candidate.get("suggested_z_index"), 20 if element_type == "sticker" else 10),
        }

    def _initial_position_for_zone(self, zone: str, element_type: str, index: int, w: int, h: int) -> tuple[int, int]:
        page_w = self.PAGE_W
        page_h = self.PAGE_H
        if zone in {"center", "lower_center"}:
            return max(0, (page_w - w) // 2), 720 if zone == "lower_center" else 380
        if zone == "top":
            return 100 + index * 220, 120
        if zone == "bottom_left":
            return 80, max(0, page_h - h - 240)
        if zone == "bottom_right":
            return max(0, page_w - w - 80), max(0, page_h - h - 240)
        if zone == "top_left":
            return 80, 160
        if zone == "top_right":
            return max(0, page_w - w - 80), 160
        if element_type == "decoration":
            positions = [(80, 120), (max(0, page_w - w - 80), 120), (80, max(0, page_h - h - 180))]
        else:
            positions = [(max(0, page_w - w - 80), 160), (80, max(0, page_h - h - 240)), (max(0, page_w - w - 80), max(0, page_h - h - 240))]
        return positions[index % len(positions)]

    def _asset_metadata_map(self, asset_context: dict) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for group in self._candidate_groups(asset_context):
            for item in group.get("items", []):
                if not isinstance(item, dict):
                    continue
                for key in ("file_url", "preview_url", "raw_file_url"):
                    url = str(item.get(key) or "").strip()
                    if url:
                        result[url] = item
        return result

    def _candidate_groups(self, asset_context: dict) -> list[dict]:
        if not isinstance(asset_context, dict):
            return []
        if not asset_context.get("selection_enforced"):
            return asset_context.get("groups", []) if isinstance(asset_context.get("groups"), list) else []
        selected = [item for item in asset_context.get("selected_materials", []) if isinstance(item, dict)]
        grouped: dict[str, list[dict]] = {"background": [], "sticker": [], "decoration": []}
        for item in selected:
            role = str(item.get("safe_role") or item.get("suggested_role") or "")
            material_type = str(item.get("material_type") or "")
            if role == "background" or material_type == "background":
                grouped["background"].append(item)
            elif role in {"focal_sticker", "supporting_sticker", "small_decoration"} or material_type == "sticker":
                grouped["sticker"].append(item)
            else:
                grouped["decoration"].append(item)
        return [{"material_type": key, "items": items} for key, items in grouped.items() if items]

    @staticmethod
    def _bind_material_props(props: dict, candidate: dict | None, *, role: str = "") -> None:
        if not isinstance(candidate, dict):
            return
        material_id = candidate.get("material_id")
        if material_id:
            props["material_id"] = material_id
        resolved_role = role or candidate.get("safe_role") or candidate.get("suggested_role")
        if resolved_role:
            props["role"] = resolved_role

    def _apply_size_hint(self, element: dict, metadata: dict, page_w: int, page_h: int) -> None:
        props = element.get("props", {})
        role = str(metadata.get("safe_role") or metadata.get("suggested_role") or props.get("role") or "")
        if role == "frame":
            inset_x = round(page_w * 0.025)
            inset_y = round(page_h * 0.02)
            props.update({"x": inset_x, "y": inset_y, "w": page_w - inset_x * 2, "h": round(page_h * 0.92)})
            return
        size_hint = str(metadata.get("suggested_size") or "").strip()
        ratio = self._coerce_ratio(metadata.get("aspect_ratio"))
        if not ratio:
            width = self._coerce_ratio(metadata.get("asset_width"))
            height = self._coerce_ratio(metadata.get("asset_height"))
            ratio = width / height if width and height else None
        current_w = self._coerce_number(props.get("w", 0), 0) or self._default_element_size(element)[0]

        if element.get("type") == "image":
            target_w = page_w
            target_h = min(900, page_h)
        else:
            target_map = {"small": 140, "medium": 220, "large": 320}
            target_w = target_map.get(size_hint, min(current_w, 240))
            target_h = target_w

        if ratio:
            target_w, target_h = self._fit_box_to_ratio(target_w, target_h, ratio, min(page_w, 360 if element.get("type") != "image" else page_w), min(page_h, 360 if element.get("type") != "image" else target_h))

        props["w"] = target_w
        props["h"] = target_h

    def _apply_zone_hint(self, element: dict, metadata: dict, page_w: int, page_h: int) -> None:
        props = element.get("props", {})
        zone = str(metadata.get("suggested_zone") or "").strip()
        w = self._coerce_number(props.get("w", 0), 0) or self._default_element_size(element)[0]
        h = self._coerce_number(props.get("h", 0), 0) or self._default_element_size(element)[1]
        zone_positions = {
            "full_bleed": (0, 0),
            "frame": (round(page_w * 0.025), round(page_h * 0.02)),
            "top": (80, 120),
            "center": ((page_w - w) // 2, 380),
            "lower_center": ((page_w - w) // 2, 760),
            "top_left": (80, 140),
            "top_right": (max(0, page_w - w - 80), 140),
            "bottom_left": (80, max(0, page_h - h - 220)),
            "bottom_right": (max(0, page_w - w - 80), max(0, page_h - h - 220)),
            "corner": (max(0, page_w - w - 96), 120),
        }
        if zone in zone_positions:
            x, y = zone_positions[zone]
            props["x"] = x
            props["y"] = y

    def _relayout_conflicting_element(
        self,
        element: dict,
        x: int,
        y: int,
        w: int,
        h: int,
        placed: list[dict],
        page_w: int,
        page_h: int,
    ) -> tuple[int, int, int, int]:
        preferred_positions = self._preferred_positions(element, page_w, page_h, w, h)
        for nx, ny in preferred_positions:
            if self._find_collision((nx, ny, w, h), placed) is None:
                return nx, ny, w, h

        for factor in (0.88, 0.76, 0.64, 0.52):
            shrunk_w = max(1, int(w * factor))
            shrunk_h = max(1, int(h * factor))
            for nx, ny in self._preferred_positions(element, page_w, page_h, shrunk_w, shrunk_h):
                if self._find_collision((nx, ny, shrunk_w, shrunk_h), placed) is None:
                    return nx, ny, shrunk_w, shrunk_h
            nx, ny = self._find_free_position(x, y, shrunk_w, shrunk_h, placed, page_w, page_h)
            if self._find_collision((nx, ny, shrunk_w, shrunk_h), placed) is None:
                return nx, ny, shrunk_w, shrunk_h

        nx, ny = self._find_free_position(x, y, w, h, placed, page_w, page_h)
        return nx, ny, w, h

    def _placement_priority(self, el: dict) -> int:
        el_type = str(el.get("type", "")).strip()
        props = el.get("props", {}) if isinstance(el.get("props"), dict) else {}
        x = self._coerce_number(props.get("x", 0), 0)
        y = self._coerce_number(props.get("y", 0), 0)
        w_default, h_default = self._default_element_size(el)
        w = self._coerce_number(props.get("w", w_default), w_default)
        h = self._coerce_number(props.get("h", h_default), h_default)
        if self._is_background_like(el, x, y, w, h):
            return 0
        if el_type in {"text", "date_tag", "mood_tag", "weather_tag"}:
            return 1
        if el_type == "image":
            return 2
        if el_type == "sticker":
            return 3
        if el_type == "decoration":
            return 4
        return 5

    def _preferred_positions(self, element: dict, page_w: int, page_h: int, w: int, h: int) -> list[tuple[int, int]]:
        el_type = str(element.get("type", "")).strip()
        if el_type == "sticker":
            return [
                (max(0, page_w - w - 80), 140),
                (80, max(0, page_h - h - 240)),
                (max(0, page_w - w - 80), max(0, page_h - h - 240)),
                (80, 180),
                (max(0, (page_w - w) // 2), 720),
            ]
        if el_type == "decoration":
            return [
                (80, 120),
                (max(0, page_w - w - 80), 120),
                (80, max(0, page_h - h - 160)),
                (max(0, page_w - w - 80), max(0, page_h - h - 160)),
            ]
        return []

    def _is_background_like(self, element: dict, x: int, y: int, w: int, h: int) -> bool:
        props = element.get("props", {}) if isinstance(element.get("props"), dict) else {}
        role = str(props.get("role") or "")
        if role in {"background", "frame"}:
            return True
        return element.get("type") == "image" and x <= 0 and y <= 0 and w >= 900 and h >= 500

    def _protect_text_readability(self, layout: dict) -> dict:
        result = copy.deepcopy(layout)
        page_w = result.get("page", {}).get("width", self.PAGE_W)
        page_h = result.get("page", {}).get("height", self.PAGE_H)
        text_types = {"text", "date_tag", "mood_tag", "weather_tag"}

        for element in result.get("elements", []):
            if not isinstance(element, dict):
                continue
            props = element.setdefault("props", {})
            x, y, w, h = self._element_box(element, page_w, page_h)
            role = str(props.get("role") or "")
            if role == "frame":
                props["opacity"] = min(self._coerce_float(props.get("opacity"), 0.72), 0.72)
                element["z_index"] = 10
                continue
            if role == "background" or self._is_background_like(element, x, y, w, h):
                props["opacity"] = min(self._coerce_float(props.get("opacity"), 0.14), 0.18)
                element["z_index"] = 0
                continue
            if element.get("type") in text_types:
                props.setdefault("color", "#3E3328")
                props.setdefault("readable", True)
                if element.get("type") == "text":
                    element["z_index"] = max(self._coerce_number(element.get("z_index", 30), 30), 35)
                else:
                    element["z_index"] = max(self._coerce_number(element.get("z_index", 40), 40), 45)

        return result

    def _fit_box_to_ratio(self, width: int, height: int, ratio: float, max_w: int, max_h: int) -> tuple[int, int]:
        width = max(1, min(width, max_w))
        height = max(1, min(height, max_h))
        if width / max(1, height) > ratio:
            width = int(height * ratio)
        else:
            height = int(width / ratio)
        if width > max_w:
            width = max_w
            height = int(width / ratio)
        if height > max_h:
            height = max_h
            width = int(height * ratio)
        return max(1, width), max(1, height)

    def _coerce_ratio(self, value) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    def _coerce_float(self, value, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
