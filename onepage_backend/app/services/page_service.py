import uuid
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.models.element import Element
from app.models.journal import Journal
from app.models.page import Page
from app.services.material_service import MaterialService


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
        normalized_journal_id = self._normalize_uuid(journal_id)
        journal = (
            await self.db.execute(
                select(Journal).where(Journal.id == normalized_journal_id, Journal.user_id == user_id)
            )
        ).scalar_one_or_none()
        if not journal:
            raise NotFoundException("Journal not found")

        page = Page(
            journal_id=normalized_journal_id,
            user_id=user_id,
            title=title,
            content_text=content_text,
            layout_json=layout_json,
            weather=weather,
            mood=mood,
            page_date=self._normalize_page_date(page_date),
        )
        self.db.add(page)
        await self.db.flush()

        if elements:
            self._batch_insert_elements(page.id, elements)

        if layout_json:
            await MaterialService(self.db).mark_used_by_urls(
                user_id=user_id,
                urls=MaterialService.extract_material_urls_from_layout(layout_json),
            )

        journal.page_count = (journal.page_count or 0) + 1
        await self.db.refresh(page)
        return page

    async def get_by_id(self, page_id: str, user_id: str) -> Page:
        q = (
            select(Page)
            .where(Page.id == self._normalize_uuid(page_id), Page.user_id == user_id)
            .options(selectinload(Page.elements))
        )
        result = (await self.db.execute(q)).scalar_one_or_none()
        if not result:
            raise NotFoundException("Page not found")
        return result

    async def update(self, page_id: str, user_id: str, data: dict) -> Page:
        page = await self.get_by_id(page_id, user_id)

        update_fields = {k: v for k, v in data.items() if k != "elements" and v is not None}
        if "page_date" in update_fields:
            update_fields["page_date"] = self._normalize_page_date(update_fields["page_date"])
        target_journal_id = update_fields.get("journal_id")
        if target_journal_id:
            normalized_target_journal_id = self._normalize_uuid(target_journal_id)
            update_fields["journal_id"] = normalized_target_journal_id
        else:
            normalized_target_journal_id = None
        if normalized_target_journal_id and normalized_target_journal_id != page.journal_id:
            target_journal = (
                await self.db.execute(
                    select(Journal).where(Journal.id == normalized_target_journal_id, Journal.user_id == user_id)
                )
            ).scalar_one_or_none()
            if not target_journal:
                raise NotFoundException("Journal not found")
            current_journal = (
                await self.db.execute(
                    select(Journal).where(Journal.id == page.journal_id, Journal.user_id == user_id)
                )
            ).scalar_one_or_none()
            if current_journal:
                current_journal.page_count = max(0, (current_journal.page_count or 1) - 1)
            target_journal.page_count = (target_journal.page_count or 0) + 1
        if update_fields:
            await self.db.execute(
                update(Page).where(Page.id == self._normalize_uuid(page_id)).values(**update_fields)
            )

        if "elements" in data and data["elements"] is not None:
            normalized_page_id = self._normalize_uuid(page_id)
            existing = (
                await self.db.execute(select(Element).where(Element.page_id == normalized_page_id))
            ).scalars().all()
            for el in existing:
                await self.db.delete(el)
            self._batch_insert_elements(normalized_page_id, data["elements"])

        if data.get("layout_json"):
            await MaterialService(self.db).mark_used_by_urls(
                user_id=user_id,
                urls=MaterialService.extract_material_urls_from_layout(data["layout_json"]),
            )

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

    def _batch_insert_elements(self, page_id: str | uuid.UUID, elements: list[dict]):
        normalized_page_id = self._normalize_uuid(page_id)
        for el_data in elements:
            el = Element(
                page_id=normalized_page_id,
                element_type=el_data["element_type"],
                props_json=el_data["props_json"],
                z_index=el_data.get("z_index", 0),
            )
            self.db.add(el)

    @staticmethod
    def _normalize_uuid(value: str | uuid.UUID) -> uuid.UUID:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))

    @staticmethod
    def _normalize_page_date(page_date: str | date | None) -> date | None:
        if page_date is None or isinstance(page_date, date):
            return page_date
        return date.fromisoformat(page_date)
