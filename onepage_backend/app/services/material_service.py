import json
import math
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import StorageException, ValidationException
from app.core.minio import minio_compose_object, minio_presigned_put_url, minio_remove_object
from app.models.material import Material
from app.models.material_user_state import MaterialUserState
from app.services.material_catalog import infer_quality_profile
from app.services.material_urls import build_material_proxy_url


class MaterialService:
    MATERIAL_PROXY_PATH_RE = re.compile(r"/materials/([0-9a-fA-F-]{36})/(?:asset|preview)(?:\?|$)")
    LAYOUT_ROLE_LIMITS = {
        "background": 5,
        "focal_sticker": 8,
        "supporting_sticker": 6,
        "decoration": 5,
        "frame": 5,
        "tape": 5,
    }
    SUBJECT_BACKGROUND_UNSAFE_TOKENS = {
        "人物",
        "人物角色",
        "人物场景",
        "猫",
        "狗",
        "动物",
        "熊",
        "鸡",
        "食物",
        "美食",
        "饺子",
        "咖啡",
    }
    SEMANTIC_QUERY_EXPANSIONS = {
        "happy": ["开心", "爱心星星", "花草", "动物", "节日符号"],
        "开心": ["happy", "爱心星星", "花草", "动物", "节日符号"],
        "excited": ["开心", "节日符号", "爱心星星", "彩虹"],
        "兴奋": ["开心", "节日符号", "爱心星星", "彩虹"],
        "calm": ["平静", "治愈", "纸张纹理", "留白底", "花草", "人物场景"],
        "平静": ["calm", "治愈", "纸张纹理", "留白底", "花草", "人物场景"],
        "healing": ["治愈", "平静", "花草", "纸张纹理", "人物场景"],
        "治愈": ["healing", "平静", "花草", "纸张纹理", "人物场景"],
        "sad": ["雨天", "天气自然", "纸张纹理", "平静"],
        "难过": ["sad", "雨天", "天气自然", "纸张纹理"],
        "sadness": ["雨天", "天气自然", "纸张纹理"],
        "nostalgic": ["复古", "牛皮纸", "装饰花纹", "纸张纹理"],
        "怀旧": ["复古", "牛皮纸", "装饰花纹", "纸张纹理"],
        "minimal": ["极简", "留白底", "网格线条", "纸张纹理"],
        "cute": ["可爱", "动物", "爱心星星", "花草"],
        "warm": ["治愈", "纸张纹理", "花草", "牛皮纸"],
        "vintage": ["复古", "牛皮纸", "装饰花纹"],
        "海边": ["beach", "sea", "ocean", "天气自然", "海边"],
        "beach": ["海边", "天气自然", "人物场景"],
        "sea": ["海边", "天气自然"],
        "ocean": ["海边", "天气自然"],
        "雨天": ["rain", "天气自然", "纸张纹理", "雨天"],
        "rain": ["雨天", "天气自然", "纸张纹理"],
        "咖啡": ["coffee", "人物场景", "小物件", "纸张纹理"],
        "coffee": ["咖啡", "人物场景", "小物件", "纸张纹理"],
        "阅读": ["read", "book", "人物场景", "纸张纹理"],
        "旅行": ["travel", "人物场景", "天气自然", "海边"],
        "家庭": ["home", "family", "人物场景"],
        "工作": ["work", "人物场景", "网格线条"],
        "露营": ["camp", "人物场景", "花草", "天气自然"],
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    def build_material_proxy_url(self, material: Material, variant: str, user_id: str | None = None) -> str:
        return build_material_proxy_url(material, variant, user_id)

    async def _attach_user_state(self, materials: list[Material], user_id: str | None) -> list[Material]:
        if not materials or not user_id:
            for material in materials:
                setattr(material, "_user_state", None)
            return materials

        material_ids = [material.id for material in materials]
        states = (
            await self.db.execute(
                select(MaterialUserState).where(
                    MaterialUserState.user_id == user_id,
                    MaterialUserState.material_id.in_(material_ids),
                )
            )
        ).scalars().all()
        state_by_material_id = {state.material_id: state for state in states}
        for material in materials:
            setattr(material, "_user_state", state_by_material_id.get(material.id))
        return materials

    async def _get_visible_material_or_raise(self, material_id: str, user_id: str) -> Material:
        material_uuid = uuid.UUID(material_id)
        material = await self.db.get(Material, material_uuid)
        if material is None or not self._is_visible_to_user(material, user_id):
            raise ValidationException("Material not found")
        setattr(material, "_user_state", None)
        return material

    async def get_visible_material(self, *, material_id: str, user_id: str | None) -> Material | None:
        material_uuid = uuid.UUID(material_id)
        material = await self.db.get(Material, material_uuid)
        if material is None or not self._is_visible_to_user(material, user_id):
            return None
        return material

    async def _get_or_create_user_state(self, material_id, user_id: str) -> MaterialUserState:
        state = (
            await self.db.execute(
                select(MaterialUserState).where(
                    MaterialUserState.material_id == material_id,
                    MaterialUserState.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if state is None:
            state = MaterialUserState(material_id=material_id, user_id=user_id, is_favorite=False)
            self.db.add(state)
            await self.db.flush()
        return state

    @staticmethod
    def extract_material_urls_from_layout(layout: dict | None) -> list[str]:
        if not isinstance(layout, dict):
            return []

        result: list[str] = []
        for element in layout.get("elements", []):
            if not isinstance(element, dict):
                continue
            props = element.get("props")
            if not isinstance(props, dict):
                continue
            url = str(props.get("url") or "").strip()
            if url and url not in result:
                result.append(url)
        return result

    async def _load_visible_materials(self, material_type: str | None = None, user_id: str | None = None) -> list[Material]:
        query = select(Material)
        if material_type:
            query = query.where(Material.material_type == material_type)
        all_materials = (await self.db.execute(query)).scalars().all()
        visible = [item for item in all_materials if self._is_visible_to_user(item, user_id)]
        return await self._attach_user_state(visible, user_id)

    async def list_materials(
        self,
        material_type: str | None = None,
        style: str | None = None,
        emotion: str | None = None,
        scene: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        query: str | None = None,
        user_id: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[Material], int]:
        all_materials = await self._load_visible_materials(material_type=material_type, user_id=user_id)

        filtered = []
        for m in all_materials:
            if category and category != "全部" and self._material_category(m) != category:
                continue
            if style and not self._matches_named_tag(style, self._material_style_tags(m)):
                continue
            if emotion and not self._matches_named_tag(emotion, self._material_emotion_tags(m)):
                continue
            if scene and not self._matches_named_tag(scene, self._material_scene_tags(m)):
                continue
            if tag and tag != "全部" and not self._matches_named_tag(tag, self._material_search_values(m)):
                continue
            if query and not self._matches_free_text(query, self._material_search_values(m)):
                continue
            filtered.append(m)

        total = len(filtered)
        start = (page - 1) * size
        materials = filtered[start:start + size]
        return materials, total

    async def list_favorites(
        self,
        *,
        user_id: str,
        material_type: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[Material], int]:
        states = (
            await self.db.execute(
                select(MaterialUserState)
                .where(MaterialUserState.user_id == user_id, MaterialUserState.is_favorite.is_(True))
                .order_by(MaterialUserState.favorited_at.desc(), MaterialUserState.updated_at.desc())
            )
        ).scalars().all()

        materials: list[Material] = []
        for state in states:
            material = await self.db.get(Material, state.material_id)
            if material is None or not self._is_visible_to_user(material, user_id):
                continue
            if material_type and material.material_type != material_type:
                continue
            setattr(material, "_user_state", state)
            materials.append(material)

        total = len(materials)
        start = (page - 1) * size
        return materials[start:start + size], total

    async def list_recent(
        self,
        *,
        user_id: str,
        material_type: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[Material], int]:
        states = (
            await self.db.execute(
                select(MaterialUserState)
                .where(MaterialUserState.user_id == user_id, MaterialUserState.last_used_at.is_not(None))
                .order_by(MaterialUserState.last_used_at.desc(), MaterialUserState.updated_at.desc())
            )
        ).scalars().all()

        materials: list[Material] = []
        for state in states:
            material = await self.db.get(Material, state.material_id)
            if material is None or not self._is_visible_to_user(material, user_id):
                continue
            if material_type and material.material_type != material_type:
                continue
            setattr(material, "_user_state", state)
            materials.append(material)

        total = len(materials)
        start = (page - 1) * size
        return materials[start:start + size], total

    async def set_favorite(self, *, material_id: str, user_id: str, is_favorite: bool) -> Material:
        material = await self._get_visible_material_or_raise(material_id, user_id)
        state = await self._get_or_create_user_state(material.id, user_id)
        state.set_favorite(is_favorite)
        await self.db.commit()
        await self.db.refresh(state)
        setattr(material, "_user_state", state)
        return material

    async def mark_used(self, *, material_id: str, user_id: str) -> Material:
        material = await self._get_visible_material_or_raise(material_id, user_id)
        state = await self._get_or_create_user_state(material.id, user_id)
        state.mark_used()
        await self.db.commit()
        await self.db.refresh(state)
        setattr(material, "_user_state", state)
        return material

    async def mark_used_by_urls(self, *, user_id: str, urls: list[str]) -> int:
        normalized_urls = [url.strip() for url in urls if url and url.strip()]
        if not normalized_urls:
            return 0

        material_ids, unresolved_urls = self._extract_material_ids_from_urls(normalized_urls)
        materials_by_id: dict[uuid.UUID, Material] = {}

        if material_ids:
            materials = (
                await self.db.execute(select(Material).where(Material.id.in_(material_ids)))
            ).scalars().all()
            materials_by_id.update({material.id: material for material in materials})

        if unresolved_urls:
            all_materials = (await self.db.execute(select(Material))).scalars().all()
            for material in all_materials:
                candidate_urls = {
                    str(material.file_url or "").strip(),
                    str((material.meta_info or {}).get("raw_file_url") or "").strip(),
                    str((material.meta_info or {}).get("preview_url") or "").strip(),
                }
                if unresolved_urls.intersection({url for url in candidate_urls if url}):
                    materials_by_id[material.id] = material

        marked = 0
        for material in materials_by_id.values():
            if not self._is_visible_to_user(material, user_id):
                continue
            state = await self._get_or_create_user_state(material.id, user_id)
            state.mark_used()
            setattr(material, "_user_state", state)
            marked += 1

        if marked:
            await self.db.flush()
        return marked

    def _extract_material_ids_from_urls(self, urls: list[str]) -> tuple[set[uuid.UUID], set[str]]:
        material_ids: set[uuid.UUID] = set()
        unresolved_urls: set[str] = set()
        for url in urls:
            match = self.MATERIAL_PROXY_PATH_RE.search(url)
            if not match:
                unresolved_urls.add(url)
                continue
            try:
                material_ids.add(uuid.UUID(match.group(1)))
            except ValueError:
                unresolved_urls.add(url)
        return material_ids, unresolved_urls

    async def recommend(
        self,
        style: str | None = None,
        emotion: str | None = None,
        scene: str | None = None,
        weather: str | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        all_materials = await self._load_visible_materials(user_id=user_id)

        scored = []
        for m in all_materials:
            score, _ = self._score_material(m, emotion=emotion, scene=scene, style=style, weather=weather, keywords=[])
            if score > 0:
                scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)

        groups: dict[str, list] = {}
        for _, m in scored:
            if m.material_type not in groups:
                groups[m.material_type] = []
            if len(groups[m.material_type]) < 6:
                groups[m.material_type].append(m)

        return [{"material_type": t, "items": items} for t, items in groups.items()]

    async def retrieve_layout_candidates(
        self,
        *,
        user_id: str | None,
        emotion: str | None,
        scene: str | None,
        style: str | None,
        weather: str | None,
        keywords: list[str] | None,
    ) -> dict:
        all_materials = await self._load_visible_materials(user_id=user_id)
        keyword_list = [item for item in (keywords or []) if item]
        scored: list[tuple[int, list[str], Material]] = []
        for material in all_materials:
            score, reasons = self._score_material(
                material,
                emotion=emotion,
                scene=scene,
                style=style,
                weather=weather,
                keywords=keyword_list,
            )
            if score <= 0:
                continue
            quality_score, quality_reasons = self._score_quality(material)
            score += quality_score
            reasons.extend(quality_reasons)
            if material.material_type == "background" and quality_score <= -5:
                continue
            preference_score, preference_reasons = self._score_user_preference(material)
            score += preference_score
            reasons.extend(preference_reasons)
            scored.append((score, reasons, material))

        scored.sort(key=lambda item: item[0], reverse=True)
        role_grouped: dict[str, list[dict]] = {key: [] for key in self.LAYOUT_ROLE_LIMITS}
        used_ids: set[str] = set()

        for score, reasons, material in scored:
            material_id = str(material.id)
            if material_id in used_ids:
                continue
            quality = self._material_quality(material)
            profile = self._material_tag_profile(material, quality=quality)
            if not self._is_valid_layout_material(material):
                continue
            role = self._primary_layout_role(material, profile)
            if role == "background" and profile["background_safe"] is False:
                continue
            bucket = role_grouped.get(role)
            if bucket is None or len(bucket) >= self.LAYOUT_ROLE_LIMITS[role]:
                continue
            item = (
                {
                    "material_id": material_id,
                    "material_type": material.material_type,
                    "source_material_type": material.material_type,
                    "file_url": self.build_material_proxy_url(material, "asset", user_id),
                    "preview_url": self.build_material_proxy_url(material, "preview", user_id),
                    "raw_file_url": (material.meta_info or {}).get("raw_file_url", material.file_url),
                    "display_name": (material.meta_info or {}).get("display_name"),
                    "origin_path": (material.meta_info or {}).get("origin_path"),
                    "asset_width": (material.meta_info or {}).get("asset_width"),
                    "asset_height": (material.meta_info or {}).get("asset_height"),
                    "aspect_ratio": (material.meta_info or {}).get("aspect_ratio"),
                    "category": self._material_category(material),
                    "tags": self._material_meta_tags(material),
                    "style_tags": self._material_style_tags(material),
                    "emotion_tags": self._material_emotion_tags(material),
                    "scene_tags": self._material_scene_tags(material),
                    "visual_style": quality["visual_style"],
                    "complexity": quality["complexity"],
                    "density": quality["density"],
                    "importance": quality["importance"],
                    "background_safe": quality["background_safe"],
                    "score": score,
                    "match_reasons": reasons,
                    "matched_tags": self._matched_tags_for_material(material, keyword_list, emotion=emotion, scene=scene, style=style, weather=weather),
                    **profile,
                }
            )
            bucket.append(item)
            used_ids.add(material_id)

        grouped = self._legacy_groups_from_roles(role_grouped)
        return {
            "summary": {
                "emotion": emotion or "",
                "scene": scene or "",
                "style": style or "",
                "weather": weather or "",
                "keywords": keyword_list,
                "role_counts": {role: len(items) for role, items in role_grouped.items()},
                "role_limits": dict(self.LAYOUT_ROLE_LIMITS),
            },
            "role_groups": [{"role": key, "items": value} for key, value in role_grouped.items() if value],
            "groups": [{"material_type": key, "items": value} for key, value in grouped.items() if value],
        }

    def _legacy_groups_from_roles(self, role_grouped: dict[str, list[dict]]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {"background": [], "sticker": [], "decoration": []}
        grouped["background"] = role_grouped.get("background", [])
        grouped["sticker"] = [*role_grouped.get("focal_sticker", []), *role_grouped.get("supporting_sticker", [])]
        grouped["decoration"] = [
            *role_grouped.get("decoration", []),
            *role_grouped.get("frame", []),
            *role_grouped.get("tape", []),
        ]
        return grouped

    def _material_tag_profile(self, material: Material, *, quality: dict | None = None) -> dict:
        meta = material.meta_info or {}
        quality = quality or self._material_quality(material)
        keywords = self._material_search_values(material)
        subject = str(meta.get("subject") or meta.get("category") or self._material_category(material) or "").strip()
        density = str(meta.get("density") or quality.get("density") or "medium").strip().lower()
        complexity = str(meta.get("complexity") or quality.get("complexity") or "medium").strip().lower()
        background_safe = meta.get("background_safe")
        if background_safe is None:
            background_safe = quality.get("background_safe")
        if background_safe is None:
            background_safe = not self._contains_any(keywords, self.SUBJECT_BACKGROUND_UNSAFE_TOKENS)
        background_safe = self._coerce_bool(background_safe, default=True)
        suggested_role = str(meta.get("suggested_role") or "").strip() or self._infer_layout_role(material, subject=subject, density=density)
        suggested_zone = str(meta.get("suggested_zone") or "").strip() or self._infer_layout_zone(suggested_role, material)
        description = str(meta.get("description") or meta.get("display_name") or meta.get("filename") or "").strip()
        return {
            "style": self._material_style_tags(material),
            "emotion": self._material_emotion_tags(material),
            "scene": self._material_scene_tags(material),
            "subject": subject,
            "color_tone": str(meta.get("color_tone") or meta.get("color") or "").strip(),
            "complexity": complexity,
            "density": density,
            "background_safe": background_safe,
            "suggested_role": suggested_role,
            "suggested_zone": suggested_zone,
            "description": description,
            "keywords": self._dedupe_preserve_order([*keywords, *self._material_semantic_tags(material)]),
        }

    def _infer_layout_role(self, material: Material, *, subject: str, density: str) -> str:
        text = " ".join(self._material_search_values(material) + [subject]).lower()
        usage_type = self._material_usage_type(material)
        category = self._material_category(material)
        if material.material_type == "background":
            return "background"
        if material.material_type == "decoration":
            if self._contains_any([text, usage_type, category], {"胶带", "tape", "丝带"}):
                return "tape"
            if self._contains_any([text, usage_type, category], {"边框", "frame", "框架", "分隔"}):
                return "frame"
            return "decoration"
        if material.material_type == "sticker":
            if self._contains_any([usage_type, category, text], {"主体", "主体贴图", "食物", "美食", "人物角色", "动物"}):
                return "focal_sticker"
            return "supporting_sticker"
        return "decoration"

    def _primary_layout_role(self, material: Material, profile: dict) -> str:
        role = str(profile.get("suggested_role") or "").strip()
        if role in self.LAYOUT_ROLE_LIMITS:
            return role
        return self._infer_layout_role(
            material,
            subject=str(profile.get("subject") or ""),
            density=str(profile.get("density") or ""),
        )

    def _infer_layout_zone(self, role: str, material: Material) -> str:
        if role == "background":
            return "full_bleed"
        if role == "focal_sticker":
            return "lower_center"
        if role == "supporting_sticker":
            return "corner"
        if role == "frame":
            return "frame"
        if role == "tape":
            return "top"
        return "corner"

    def _is_valid_layout_material(self, material: Material) -> bool:
        meta = material.meta_info or {}
        url = str(material.file_url or meta.get("raw_file_url") or meta.get("preview_url") or "").strip()
        if not url:
            return False
        width = meta.get("asset_width")
        height = meta.get("asset_height")
        try:
            if width is not None and float(width) <= 0:
                return False
            if height is not None and float(height) <= 0:
                return False
        except (TypeError, ValueError):
            return False
        return True

    def _matched_tags_for_material(
        self,
        material: Material,
        keywords: list[str],
        *,
        emotion: str | None,
        scene: str | None,
        style: str | None,
        weather: str | None,
    ) -> list[str]:
        values = self._material_search_values(material)
        probes = self._expand_query_terms(emotion, scene, style, weather, *keywords)
        matches: list[str] = []
        for probe in probes:
            lowered = probe.lower()
            if lowered and any(lowered in value.lower() or value.lower() in lowered for value in values):
                matches.append(probe)
        return self._dedupe_preserve_order(matches)

    @staticmethod
    def _contains_any(values: list[str] | set[str], tokens: set[str]) -> bool:
        haystack = " ".join(str(value or "") for value in values).lower()
        return any(str(token).lower() in haystack for token in tokens)

    @staticmethod
    def _coerce_bool(value, *, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in {"true", "1", "yes", "y"}:
            return True
        if text in {"false", "0", "no", "n"}:
            return False
        return default

    def _score_user_preference(self, material: Material) -> tuple[int, list[str]]:
        state = getattr(material, "_user_state", None)
        if state is None:
            return 0, []

        score = 0
        reasons: list[str] = []
        if getattr(state, "is_favorite", False):
            score += 3
            reasons.append("preference:favorite")

        if getattr(state, "last_used_at", None):
            score += 2
            reasons.append("preference:recent")

        return score, reasons

    def _is_visible_to_user(self, material: Material, user_id: str | None) -> bool:
        visibility = ((material.meta_info or {}).get("visibility")) or "public"
        owner_user_id = (material.meta_info or {}).get("owner_user_id")
        return not (visibility == "private" and owner_user_id and owner_user_id != user_id)

    def _material_meta_tags(self, material: Material) -> list[str]:
        meta_tags = (material.meta_info or {}).get("tags") or []
        return [str(item) for item in meta_tags if str(item).strip()]

    def _material_category(self, material: Material) -> str:
        return str((material.meta_info or {}).get("category") or "")

    def _material_sub_category(self, material: Material) -> str:
        return str((material.meta_info or {}).get("sub_category") or "")

    def _material_usage_type(self, material: Material) -> str:
        return str((material.meta_info or {}).get("usage_type") or "")

    def _material_semantic_tags(self, material: Material) -> list[str]:
        semantic_tags = (material.meta_info or {}).get("semantic_tags") or []
        return self._normalize_tags(semantic_tags if isinstance(semantic_tags, list) else [])

    def _material_search_values(self, material: Material) -> list[str]:
        meta = material.meta_info or {}
        return self._normalize_tags([
            material.material_type,
            self._material_category(material),
            self._material_sub_category(material),
            self._material_usage_type(material),
            str(meta.get("display_name") or ""),
            str(meta.get("filename") or ""),
            str(meta.get("target_path") or ""),
            *self._material_meta_tags(material),
            *self._material_semantic_tags(material),
            *self._material_style_tags(material),
            *self._material_emotion_tags(material),
            *self._material_scene_tags(material),
        ])

    def _material_style_tags(self, material: Material) -> list[str]:
        return self._normalize_tags([*(material.style_tags or []), *self._material_meta_tags(material)])

    def _material_emotion_tags(self, material: Material) -> list[str]:
        return self._normalize_tags([*(material.emotion_tags or []), self._material_category(material), *self._material_meta_tags(material)])

    def _material_scene_tags(self, material: Material) -> list[str]:
        return self._normalize_tags([*(material.scene_tags or []), self._material_category(material), *self._material_meta_tags(material)])

    def _material_quality(self, material: Material) -> dict:
        meta = material.meta_info or {}
        existing = {
            "visual_style": meta.get("visual_style"),
            "complexity": meta.get("complexity"),
            "density": meta.get("density"),
            "importance": meta.get("importance"),
            "background_safe": meta.get("background_safe"),
            "semantic_blocked": meta.get("semantic_blocked"),
        }
        if all(value is not None for value in existing.values()):
            return existing

        origin_path = str(meta.get("origin_path") or "")
        parts = origin_path.split("/")
        provider = str(meta.get("provider") or (parts[0] if parts else "user"))
        directory_name = parts[1] if len(parts) > 1 else provider
        keywords = [
            str(meta.get("display_name") or ""),
            origin_path,
            *self._material_meta_tags(material),
            *self._material_style_tags(material),
            *self._material_scene_tags(material),
        ]
        inferred = infer_quality_profile(
            material_type=material.material_type,
            category=self._material_category(material),
            provider=provider,
            directory_name=directory_name,
            keywords=keywords,
        )
        return {
            "visual_style": existing["visual_style"] or inferred["visual_style"],
            "complexity": existing["complexity"] or inferred["complexity"],
            "density": existing["density"] or inferred["density"],
            "importance": existing["importance"] or inferred["importance"],
            "background_safe": existing["background_safe"] if existing["background_safe"] is not None else inferred["background_safe"],
            "semantic_blocked": existing["semantic_blocked"] if existing["semantic_blocked"] is not None else inferred["semantic_blocked"],
        }

    def _normalize_tags(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered not in result:
                result.append(lowered)
        return result

    def _matches_named_tag(self, expected: str, tags: list[str]) -> bool:
        expected_lower = expected.strip().lower()
        return any(expected_lower == tag or expected_lower in tag or tag in expected_lower for tag in tags)

    @classmethod
    def _expand_query_terms(cls, *values: str | None) -> list[str]:
        result: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            candidates = [text, *cls.SEMANTIC_QUERY_EXPANSIONS.get(text, [])]
            lowered = text.lower()
            candidates.extend(cls.SEMANTIC_QUERY_EXPANSIONS.get(lowered, []))
            for candidate in candidates:
                candidate_text = str(candidate).strip()
                if candidate_text and candidate_text not in result:
                    result.append(candidate_text)
        return result

    def _matches_any_named_tag(self, expected_terms: list[str], tags: list[str]) -> str | None:
        for term in expected_terms:
            if self._matches_named_tag(term, tags):
                return term
        return None

    def _matches_free_text(self, query: str, values: list[str]) -> bool:
        query_lower = query.strip().lower()
        if not query_lower:
            return True
        return any(query_lower in value.lower() for value in values)

    def _score_material(
        self,
        material: Material,
        *,
        emotion: str | None,
        scene: str | None,
        style: str | None,
        weather: str | None,
        keywords: list[str],
    ) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []

        emotion_terms = self._expand_query_terms(emotion)
        scene_terms = self._expand_query_terms(scene)
        style_terms = self._expand_query_terms(style)
        weather_terms = self._expand_query_terms(weather)

        emotion_match = self._matches_any_named_tag(emotion_terms, self._material_emotion_tags(material))
        scene_match = self._matches_any_named_tag(scene_terms, self._material_scene_tags(material))
        style_match = self._matches_any_named_tag(style_terms, self._material_style_tags(material))
        weather_match = self._matches_any_named_tag(weather_terms, self._material_scene_tags(material))

        if emotion_match:
            score += 3
            reasons.append(f"emotion:{emotion_match}")
        if scene_match:
            score += 6
            reasons.append(f"scene:{scene_match}")
            category = self._material_category(material).strip().lower()
            if category and any(category == term.strip().lower() for term in scene_terms):
                score += 3
                reasons.append(f"scene_category:{self._material_category(material)}")
        if style_match:
            score += 1
            reasons.append(f"style:{style_match}")
        if weather_match:
            score += 3
            reasons.append(f"weather:{weather_match}")

        searchable = {
            self._material_category(material).lower(),
            *self._material_meta_tags(material),
            *self._material_style_tags(material),
            *self._material_emotion_tags(material),
            *self._material_scene_tags(material),
        }
        searchable = {item.lower() for item in searchable if item}
        expanded_keywords = self._expand_query_terms(*keywords)
        for keyword in expanded_keywords:
            lowered = keyword.lower()
            if any(lowered in item or item in lowered for item in searchable):
                score += 2
                reasons.append(f"keyword:{keyword}")

        if material.material_type == "background":
            if scene or weather:
                score += 1
        elif material.material_type == "decoration":
            if style or keywords:
                score += 1
        elif material.material_type == "sticker":
            if emotion:
                score += 1

        return score, reasons

    def _score_quality(self, material: Material) -> tuple[int, list[str]]:
        quality = self._material_quality(material)
        score = 0
        reasons: list[str] = []

        if quality.get("semantic_blocked"):
            return -20, ["quality:semantic_blocked"]

        if material.material_type == "background":
            if quality.get("background_safe"):
                score += 8
                reasons.append("quality:background_safe")
            else:
                score -= 6
                reasons.append("quality:background_not_safe")
            if quality.get("density") == "low":
                score += 4
                reasons.append("quality:low_density")
            elif quality.get("density") == "high":
                score -= 8
                reasons.append("quality:high_density")
            if quality.get("complexity") == "low":
                score += 2
            elif quality.get("complexity") == "high":
                score -= 4
        else:
            if quality.get("density") == "high":
                score -= 2
                reasons.append("quality:high_density")
            if quality.get("importance") in {"focal", "decorative"}:
                score += 1
        return score, reasons

    @staticmethod
    def derive_material_tags(material_type: str, category: str, tags: list[str]) -> tuple[list[str], list[str], list[str]]:
        normalized_tags = [item.strip() for item in tags if item.strip()]
        category_text = category.strip()
        combined = [item for item in [category_text, *normalized_tags] if item]

        style_vocab = {"线稿", "手绘", "插画", "装饰", "复古", "可爱", "极简"}
        emotion_vocab = {"开心", "治愈", "平静", "独处", "节日", "happy", "healing", "calm", "solo", "holiday"}
        scene_vocab = {"海边", "雨天", "咖啡", "阅读", "工作", "旅行", "家庭", "露营"}

        style_tags = [item for item in combined if item in style_vocab]
        emotion_tags = [item for item in combined if item in emotion_vocab]
        scene_tags = [item for item in combined if item in scene_vocab]

        if material_type == "background" and category_text in {"纸张纹理", "网格线条", "牛皮纸", "水彩", "留白底", "森系", "海边", "雨天"}:
            scene_tags.insert(0, category_text)
        elif material_type == "decoration":
            style_tags.insert(0, "装饰")
        elif material_type == "sticker" and category_text == "人物场景":
            style_tags.insert(0, "插画")

        return (
            MaterialService._dedupe_preserve_order(style_tags),
            MaterialService._dedupe_preserve_order(emotion_tags),
            MaterialService._dedupe_preserve_order(scene_tags),
        )

    @staticmethod
    def extract_candidate_keywords(*values: str) -> list[str]:
        raw = " ".join(value for value in values if value)
        tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", raw)
        stopwords = {"今天", "我们", "他们", "然后", "感觉", "因为", "所以", "一个", "一些", "真的", "非常", "自己", "周末"}
        result: list[str] = []
        for token in tokens:
            if token in stopwords:
                continue
            if token not in result:
                result.append(token)
        return result[:12]

    @staticmethod
    def _dedupe_preserve_order(values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if value and value not in result:
                result.append(value)
        return result


class MaterialUploadService:
    CHUNK_SIZE = 8 * 1024 * 1024
    MAX_FILE_SIZE = 500 * 1024 * 1024
    SESSION_TTL_SECONDS = 3600

    def __init__(self, db: AsyncSession, redis_client: aioredis.Redis):
        self.db = db
        self.redis = redis_client

    async def create_upload_session(
        self,
        user_id: str,
        file_name: str,
        file_size: int,
        mime_type: str,
        material_type: str,
        category: str,
        tags: list[str],
        visibility: str,
    ) -> dict:
        if mime_type not in settings.ALLOWED_IMAGE_TYPES:
            raise ValidationException(f"Unsupported file type: {mime_type}")
        if file_size > self.MAX_FILE_SIZE:
            raise ValidationException("File too large, max 500MB")
        if material_type not in {"sticker", "background", "decoration"}:
            raise ValidationException("Unsupported material_type")
        if visibility not in {"private", "public"}:
            raise ValidationException("Unsupported visibility")

        ext = os.path.splitext(file_name or "file")[1] or ".bin"
        session_id = uuid.uuid4().hex
        upload_id = uuid.uuid4().hex
        object_key = f"materials/{user_id}/{material_type}/{date.today().year}/{date.today().month:02d}/{uuid.uuid4().hex}{ext}"

        total_parts = max(1, math.ceil(file_size / self.CHUNK_SIZE))
        part_keys = [f"tmp/material_upload/{session_id}/part-{idx:05d}" for idx in range(total_parts)]
        part_urls = [minio_presigned_put_url(settings.MINIO_BUCKET_MATERIALS, key, self.SESSION_TTL_SECONDS) for key in part_keys]
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.SESSION_TTL_SECONDS)

        session_payload = {
            "session_id": session_id,
            "upload_id": upload_id,
            "user_id": user_id,
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": mime_type,
            "material_type": material_type,
            "category": category,
            "tags": tags,
            "visibility": visibility,
            "object_key": object_key,
            "part_keys": part_keys,
            "chunk_size": self.CHUNK_SIZE,
            "total_parts": total_parts,
            "expires_at": expires_at.isoformat(),
        }
        await self.redis.setex(self._session_key(session_id), self.SESSION_TTL_SECONDS, json.dumps(session_payload, ensure_ascii=False))
        return {
            "session_id": session_id,
            "upload_id": upload_id,
            "object_key": object_key,
            "chunk_size": self.CHUNK_SIZE,
            "total_parts": total_parts,
            "part_urls": part_urls,
            "expires_at": expires_at.isoformat(),
        }

    async def complete_upload_session(self, user_id: str, session_id: str) -> Material:
        payload = await self._load_session(session_id)
        if payload["user_id"] != user_id:
            raise ValidationException("Session owner mismatch")

        file_url = minio_compose_object(
            settings.MINIO_BUCKET_MATERIALS,
            payload["object_key"],
            payload["part_keys"],
        )
        preview_url = file_url if payload["mime_type"] == "image/svg+xml" else None
        for part_key in payload["part_keys"]:
            try:
                minio_remove_object(settings.MINIO_BUCKET_MATERIALS, part_key)
            except Exception:
                pass

        style_tags, emotion_tags, scene_tags = MaterialService.derive_material_tags(
            payload["material_type"],
            payload["category"],
            payload["tags"],
        )

        material = Material(
            material_type=payload["material_type"],
            style_tags=style_tags,
            emotion_tags=emotion_tags,
            scene_tags=scene_tags,
            file_url=file_url,
            meta_info={
                "owner_user_id": user_id,
                "visibility": payload["visibility"],
                "category": payload["category"],
                "tags": payload["tags"],
                "source": "user_upload",
                "upload_id": payload["upload_id"],
                "preview_url": preview_url,
                "raw_file_url": file_url,
                "mime_type": payload["mime_type"],
            },
        )
        self.db.add(material)
        await self.db.flush()
        await self.db.refresh(material)
        await self.redis.delete(self._session_key(session_id))
        return material

    async def cancel_upload_session(self, user_id: str, session_id: str):
        payload = await self._load_session(session_id)
        if payload["user_id"] != user_id:
            raise ValidationException("Session owner mismatch")
        for part_key in payload["part_keys"]:
            try:
                minio_remove_object(settings.MINIO_BUCKET_MATERIALS, part_key)
            except Exception:
                pass
        await self.redis.delete(self._session_key(session_id))

    def _session_key(self, session_id: str) -> str:
        return f"material_upload_session:{session_id}"

    async def _load_session(self, session_id: str) -> dict:
        raw = await self.redis.get(self._session_key(session_id))
        if not raw:
            raise StorageException("Upload session not found or expired")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StorageException("Invalid upload session payload") from exc
