from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.common import UnifiedResponse
from app.schemas.page import CreatePageRequest, UpdatePageRequest, PageDetailResponse, PageResponse, ElementResponse
from app.services.page_service import PageService

router = APIRouter()


@router.post("", response_model=UnifiedResponse[PageResponse])
async def create_page(
    body: CreatePageRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = PageService(db)
    elements_raw = [e.model_dump() for e in body.elements] if body.elements else None
    page = await svc.create(
        user_id=user_id, journal_id=body.journal_id, title=body.title,
        content_text=body.content_text, layout_json=body.layout_json,
        elements=elements_raw, weather=body.weather, mood=body.mood,
        page_date=body.page_date,
    )
    return UnifiedResponse(data=_page_to_response(page))


@router.get("/{page_id}", response_model=UnifiedResponse[PageDetailResponse])
async def get_page(
    page_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = PageService(db)
    page = await svc.get_by_id(page_id, user_id)
    elements = [
        ElementResponse(
            id=str(el.id), page_id=str(el.page_id), element_type=el.element_type,
            props_json=el.props_json, z_index=el.z_index, created_at=el.created_at,
        )
        for el in (page.elements or [])
    ]
    resp = _page_to_response(page)
    return UnifiedResponse(data=PageDetailResponse(**resp.model_dump(), elements=elements))


@router.put("/{page_id}", response_model=UnifiedResponse[PageResponse])
async def update_page(
    page_id: str,
    body: UpdatePageRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = PageService(db)
    data = body.model_dump(exclude_none=True)
    if body.elements is not None:
        data["elements"] = [e.model_dump() for e in body.elements]
    page = await svc.update(page_id, user_id, data)
    return UnifiedResponse(data=_page_to_response(page))


@router.delete("/{page_id}", response_model=UnifiedResponse[dict])
async def delete_page(
    page_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = PageService(db)
    await svc.delete(page_id, user_id)
    return UnifiedResponse(data={"message": "deleted"})


def _page_to_response(page) -> PageResponse:
    return PageResponse(
        id=str(page.id), journal_id=str(page.journal_id), user_id=page.user_id,
        title=page.title, content_text=page.content_text,
        layout_json=page.layout_json, thumbnail_url=page.thumbnail_url,
        weather=page.weather, mood=page.mood,
        page_date=str(page.page_date) if page.page_date else None,
        created_at=page.created_at, updated_at=page.updated_at,
    )
