import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.models.element import Element
from app.models.journal import Journal
from app.models.page import Page


class PageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: str,
        journal_id: str,
        title: str | None = None,
        content_text: str | None = None,
        layout_json: dict | None = None,
        elements: list[dict] | None = None,
        weather: dict | None = None,
        mood: str | None = None,
        page_date: str | None = None,
    ) -> Page:
        journal = (
            await self.db.execute(select(Journal).where(Journal.id == journal_id, Journal.user_id == user_id))
        ).scalar_one_or_none()
        if not journal:
            raise NotFoundException("Journal not found")

        page = Page(
            journal_id=journal_id,
            user_id=user_id,
            title=title,
            content_text=content_text,
            layout_json=layout_json,
            weather=weather,
            mood=mood,
            page_date=page_date,
        )
        self.db.add(page)
        await self.db.flush()

        if elements:
            self._batch_insert_elements(page.id, elements)

        journal.page_count = (journal.page_count or 0) + 1
        await self.db.refresh(page)
        return page

    async def get_by_id(self, page_id: str, user_id: str) -> Page:
        q = (
            select(Page)
            .where(Page.id == page_id, Page.user_id == user_id)
            .options(selectinload(Page.elements))
        )
        result = (await self.db.execute(q)).scalar_one_or_none()
        if not result:
            raise NotFoundException("Page not found")
        return result

    async def update(self, page_id: str, user_id: str, data: dict) -> Page:
        page = await self.get_by_id(page_id, user_id)

        update_fields = {k: v for k, v in data.items() if k != "elements" and v is not None}
        if update_fields:
            await self.db.execute(update(Page).where(Page.id == page_id).values(**update_fields))

        if "elements" in data and data["elements"] is not None:
            await self.db.execute(
                select(Element).where(Element.page_id == page_id)
            )
            existing = (await self.db.execute(select(Element).where(Element.page_id == page_id))).scalars().all()
            for el in existing:
                await self.db.delete(el)
            self._batch_insert_elements(page_id, data["elements"])

        await self.db.refresh(page)
        return page

    async def delete(self, page_id: str, user_id: str) -> None:
        page = await self.get_by_id(page_id, user_id)
        journal_q = select(Journal).where(Journal.id == page.journal_id)
        journal = (await self.db.execute(journal_q)).scalar_one_or_none()
        if journal:
            journal.page_count = max(0, (journal.page_count or 1) - 1)
        await self.db.delete(page)
        await self.db.flush()

    def _batch_insert_elements(self, page_id: str, elements: list[dict]):
        for el_data in elements:
            el = Element(
                page_id=page_id,
                element_type=el_data["element_type"],
                props_json=el_data["props_json"],
                z_index=el_data.get("z_index", 0),
            )
            self.db.add(el)
