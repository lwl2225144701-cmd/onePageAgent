from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.common import PaginatedResponse, PaginationMeta, UnifiedResponse
from app.schemas.journal import CreateJournalRequest, JournalResponse, JournalDetailResponse
from app.services.journal_service import JournalService

router = APIRouter()


@router.post("", response_model=UnifiedResponse[JournalResponse])
async def create_journal(
    body: CreateJournalRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = JournalService(db)
    journal = await svc.create(user_id, body.name, body.cover_url, body.settings)
    return UnifiedResponse(data=JournalResponse(
        id=str(journal.id),
        user_id=journal.user_id,
        name=journal.name,
        cover_url=journal.cover_url,
        page_count=journal.page_count,
        settings=journal.settings,
        created_at=journal.created_at,
        updated_at=journal.updated_at,
    ))


@router.get("", response_model=UnifiedResponse[PaginatedResponse[JournalResponse]])
async def list_journals(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = JournalService(db)
    journals, total = await svc.list_by_user(user_id, page, size)
    items = [
        JournalResponse(
            id=str(j.id), user_id=j.user_id, name=j.name, cover_url=j.cover_url,
            page_count=j.page_count, settings=j.settings,
            created_at=j.created_at, updated_at=j.updated_at,
        )
        for j in journals
    ]
    total_pages = (total + size - 1) // size if total > 0 else 0
    return UnifiedResponse(data=PaginatedResponse(
        data=items,
        pagination=PaginationMeta(page=page, size=size, total=total, total_pages=total_pages),
    ))


@router.get("/{journal_id}", response_model=UnifiedResponse[JournalDetailResponse])
async def get_journal(
    journal_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.page import PageBriefResponse
    svc = JournalService(db)
    journal = await svc.get_by_id(journal_id, user_id)
    pages_brief = [
        PageBriefResponse(
            id=str(p.id), title=p.title, thumbnail_url=p.thumbnail_url,
            mood=p.mood, page_date=str(p.page_date) if p.page_date else None,
            created_at=p.created_at,
        )
        for p in (journal.pages or [])
    ]
    return UnifiedResponse(data=JournalDetailResponse(
        id=str(journal.id), user_id=journal.user_id, name=journal.name,
        cover_url=journal.cover_url, page_count=journal.page_count,
        settings=journal.settings, created_at=journal.created_at,
        updated_at=journal.updated_at, pages=pages_brief,
    ))


@router.delete("/{journal_id}", response_model=UnifiedResponse[dict])
async def delete_journal(
    journal_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = JournalService(db)
    await svc.delete(journal_id, user_id)
    return UnifiedResponse(data={"message": "deleted"})
