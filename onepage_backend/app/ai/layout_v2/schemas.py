from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ai.layout_v2.enums import MaterialRole


ContentType = Literal["short_note", "medium_journal", "long_journal"]
ContentLength = Literal["short", "medium", "long"]
Density = Literal["low", "medium", "high"]


class VisualBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic: str = "日常记录"
    content_type: ContentType = "short_note"
    scene: str = "daily_life"
    sub_scene: str = "general_daily"
    primary_subject: str = ""
    primary_action: str = ""
    environment: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    emotion: str = "neutral"
    visual_keywords: list[str] = Field(default_factory=list)
    required_concepts: list[str] = Field(default_factory=list)
    excluded_concepts: list[str] = Field(default_factory=list)
    title_hint: str = "今天的一页"
    content_length: ContentLength = "short"
    preferred_density: Literal["low", "medium"] = "low"
    preferred_color_tone: list[str] = Field(default_factory=lambda: ["warm", "soft"])

    @field_validator(
        "environment",
        "objects",
        "visual_keywords",
        "required_concepts",
        "excluded_concepts",
        "preferred_color_tone",
        mode="before",
    )
    @classmethod
    def normalize_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        result: list[str] = []
        seen: set[str] = set()
        for item in values:
            text = str(item or "").strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                result.append(text)
        return result

    @model_validator(mode="after")
    def keep_emotion_out_of_subject_concepts(self) -> "VisualBrief":
        emotion = self.emotion.strip().lower()
        if emotion:
            self.required_concepts = [item for item in self.required_concepts if item.strip().lower() != emotion]
        excluded = {item.lower() for item in self.excluded_concepts}
        self.required_concepts = [item for item in self.required_concepts if item.lower() not in excluded]
        return self


class VisualBBox(BaseModel):
    model_config = ConfigDict(extra="ignore")

    x: float = 0.0
    y: float = 0.0
    w: float = 1.0
    h: float = 1.0

    @model_validator(mode="after")
    def validate_box(self) -> "VisualBBox":
        values = (self.x, self.y, self.w, self.h)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("visual_bbox must contain finite numbers")
        if self.x < 0 or self.y < 0 or self.w <= 0 or self.h <= 0:
            raise ValueError("visual_bbox must be positive and normalized")
        if self.x + self.w > 1.0001 or self.y + self.h > 1.0001:
            raise ValueError("visual_bbox exceeds image bounds")
        return self


class MaterialVisualMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subjects: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    scenes: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    detected_text: str = ""
    text_heavy: bool = False
    risk_flags: list[str] = Field(default_factory=list)
    suggested_role: MaterialRole = MaterialRole.NONE
    background_safe: bool = False
    visual_style: str = ""
    color_tone: str = ""
    complexity: Density = "medium"
    density: Density = "medium"
    visual_bbox: VisualBBox = Field(default_factory=VisualBBox)
    manual_override: bool = False
    annotation_version: str = "v2"

    @field_validator("subjects", "actions", "scenes", "objects", "risk_flags", mode="before")
    @classmethod
    def normalize_metadata_list(cls, value: Any) -> list[str]:
        return VisualBrief.normalize_list(value)


class MaterialCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    material_id: str
    role: MaterialRole
    file_url: str
    preview_url: str = ""
    raw_file_url: str = ""
    mime_type: str = ""
    semantic_score: float = 0.0
    style_score: float = 0.0
    total_score: float = 0.0
    match_reasons: list[str] = Field(default_factory=list)
    metadata: MaterialVisualMetadata
    category: str = ""
    display_name: str = ""
    asset_width: float | None = None
    asset_height: float | None = None


class LayoutPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    template_id: str
    materials: dict[str, MaterialCandidate] = Field(default_factory=dict)
    title: str
    score: float = 0.0
    fallback_reason: str = ""

    @field_validator("materials")
    @classmethod
    def material_keys_match_roles(cls, materials: dict[str, MaterialCandidate]) -> dict[str, MaterialCandidate]:
        for role, candidate in materials.items():
            if role != candidate.role.value:
                raise ValueError(f"material role mismatch: {role}")
        return materials
