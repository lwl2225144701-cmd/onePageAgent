import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.models.journal import Journal
from app.models.page import Page


class JournalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: str, name: str, cover_url: str | None = None, settings: dict | None = None) -> Journal:
        journal = Journal(user_id=user_id, name=name, cover_url=cover_url, settings=settings)
        self.db.add(journal)
        await self.db.flush()
        await self.db.refresh(journal)
        return journal

    async def list_by_user(self, user_id: str, page: int = 1, size: int = 20) -> tuple[list[Journal], int]:
        count_q = select(func.count(Journal.id)).where(Journal.user_id == user_id)
        total = (await self.db.execute(count_q)).scalar() or 0

        q = (
            select(Journal)
            .where(Journal.user_id == user_id)
            .order_by(Journal.updated_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        journals = (await self.db.execute(q)).scalars().all()
        return list(journals), total

    async def get_by_id(self, journal_id: str, user_id: str) -> Journal:
        q = (
            select(Journal)
            .where(Journal.id == journal_id, Journal.user_id == user_id)
            .options(selectinload(Journal.pages))
        )
        result = (await self.db.execute(q)).scalar_one_or_none()
        if not result:
            raise NotFoundException("Journal not found")
        return result

    async def delete(self, journal_id: str, user_id: str) -> None:
        journal = await self.get_by_id(journal_id, user_id)
        await self.db.delete(journal)
        await self.db.flush()


# Add relationship on Journal for eager loading
Journal.pages = None  # Will be set up properly via relationship
