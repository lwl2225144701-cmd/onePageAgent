from typing import Any

from app.config import settings
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.journal import JournalDetailResponse, JournalResponse
from app.schemas.material import MaterialGroup, MaterialResponse
from app.schemas.page import ElementResponse, PageBriefResponse, PageDetailResponse, PageResponse
from app.schemas.preference import UserPreferenceResponse


def to_paginated_response(*, items: list[Any], page: int, size: int, total: int) -> PaginatedResponse[Any]:
    total_pages = (total + size - 1) // size if total > 0 else 0
    return PaginatedResponse(
        data=items,
        pagination=PaginationMeta(page=page, size=size, total=total, total_pages=total_pages),
    )


def _build_material_proxy_url(material, variant: str, user_id: str | None = None) -> str:
    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    url = f"{base}/materials/{material.id}/{variant}"
    params: list[str] = []
    if user_id:
        params.append(f"anonymous_user_id={user_id}")
    version_source = getattr(material, "updated_at", None) or getattr(material, "created_at", None)
    if version_source is not None:
        params.append(f"v={int(version_source.timestamp())}")
    if params:
        url = f"{url}?{'&'.join(params)}"
    return url


def to_material_response(material, user_id: str | None = None) -> MaterialResponse:
    state = getattr(material, "_user_state", None)
    return MaterialResponse(
        id=str(material.id),
        material_type=material.material_type,
        style_tags=material.style_tags,
        emotion_tags=material.emotion_tags,
        scene_tags=material.scene_tags,
        file_url=_build_material_proxy_url(material, "asset", user_id),
        preview_url=_build_material_proxy_url(material, "preview", user_id),
        raw_file_url=(material.meta_info or {}).get("raw_file_url", material.file_url),
        mime_type=(material.meta_info or {}).get("mime_type"),
        meta_info=material.meta_info,
        is_favorite=bool(getattr(state, "is_favorite", False)),
        last_used_at=getattr(state, "last_used_at", None),
        created_at=material.created_at,
    )


def to_material_group_response(group: dict, user_id: str | None = None) -> MaterialGroup:
    return MaterialGroup(
        material_type=group["material_type"],
        items=[to_material_response(item, user_id) for item in group["items"]],
    )


def to_page_response(page) -> PageResponse:
    return PageResponse(
        id=str(page.id),
        journal_id=str(page.journal_id),
        user_id=page.user_id,
        title=page.title,
        content_text=page.content_text,
        layout_json=page.layout_json,
        thumbnail_url=page.thumbnail_url,
        weather=page.weather,
        mood=page.mood,
        page_date=str(page.page_date) if page.page_date else None,
        created_at=page.created_at,
        updated_at=page.updated_at,
    )


def to_element_response(element) -> ElementResponse:
    return ElementResponse(
        id=str(element.id),
        page_id=str(element.page_id),
        element_type=element.element_type,
        props_json=element.props_json,
        z_index=element.z_index,
        created_at=element.created_at,
    )


def to_page_detail_response(page) -> PageDetailResponse:
    page_response = to_page_response(page)
    return PageDetailResponse(
        **page_response.model_dump(),
        elements=[to_element_response(item) for item in (page.elements or [])],
    )


def to_page_brief_response(page) -> PageBriefResponse:
    return PageBriefResponse(
        id=str(page.id),
        title=page.title,
        thumbnail_url=page.thumbnail_url,
        mood=page.mood,
        page_date=str(page.page_date) if page.page_date else None,
        created_at=page.created_at,
    )


def to_journal_response(journal) -> JournalResponse:
    return JournalResponse(
        id=str(journal.id),
        user_id=journal.user_id,
        name=journal.name,
        cover_url=journal.cover_url,
        page_count=journal.page_count,
        settings=journal.settings,
        created_at=journal.created_at,
        updated_at=journal.updated_at,
    )


def to_journal_detail_response(journal) -> JournalDetailResponse:
    journal_response = to_journal_response(journal)
    return JournalDetailResponse(
        **journal_response.model_dump(),
        pages=[to_page_brief_response(page) for page in (journal.pages or [])],
    )


def to_preference_response(preferences) -> UserPreferenceResponse:
    return UserPreferenceResponse(
        id=str(preferences.id),
        user_id=preferences.user_id,
        style_preferences=preferences.style_preferences,
        font_preferences=preferences.font_preferences,
        color_preferences=preferences.color_preferences,
        behavior_stats=preferences.behavior_stats,
        created_at=preferences.created_at,
        updated_at=preferences.updated_at,
    )
