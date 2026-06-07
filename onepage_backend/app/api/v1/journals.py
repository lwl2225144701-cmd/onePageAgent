from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.serializers import to_journal_detail_response, to_journal_response, to_paginated_response
from app.api.deps import get_current_user, get_db
from app.schemas.common import PaginatedResponse, UnifiedResponse
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
    return UnifiedResponse(data=to_journal_response(journal))


@router.get("", response_model=UnifiedResponse[PaginatedResponse[JournalResponse]])
async def list_journals(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = JournalService(db)
    journals, total = await svc.list_by_user(user_id, page, size)
    items = [to_journal_response(item) for item in journals]
    return UnifiedResponse(data=to_paginated_response(items=items, page=page, size=size, total=total))


@router.get("/{journal_id}", response_model=UnifiedResponse[JournalDetailResponse])
async def get_journal(
    journal_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = JournalService(db)
    journal = await svc.get_by_id(journal_id, user_id)
    return UnifiedResponse(data=to_journal_detail_response(journal))


@router.delete("/{journal_id}", response_model=UnifiedResponse[dict])
async def delete_journal(
    journal_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = JournalService(db)
    await svc.delete(journal_id, user_id)
    return UnifiedResponse(data={"message": "deleted"})
