import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.models.journal import Journal
from app.models.page import Page
from app.models.element import Element
from app.services.page_service import PageService


@pytest.mark.asyncio
async def test_create_page_with_elements(db_session):
    journal = Journal(id=uuid.uuid4(), user_id="test_user", name="Test Journal")
    db_session.add(journal)
    await db_session.flush()

    page = Page(
        id=uuid.uuid4(), journal_id=journal.id, user_id="test_user",
        title="Test Page", mood="开心",
        layout_json={"page": {"width": 1080, "height": 1920}},
    )
    db_session.add(page)
    await db_session.flush()

    assert page.title == "Test Page"
    assert page.mood == "开心"

    el = Element(page_id=page.id, element_type="text", props_json={"content": "Hello"}, z_index=30)
    db_session.add(el)
    await db_session.flush()

    result = (await db_session.execute(select(Element).where(Element.page_id == page.id))).scalars().all()
    assert len(result) == 1
    assert result[0].element_type == "text"


@pytest.mark.asyncio
async def test_update_page_moves_between_journals_and_keeps_counts_in_sync(db_session):
    old_journal = Journal(id=uuid.uuid4(), user_id="test_user", name="2024 手账本", page_count=1)
    current_journal = Journal(id=uuid.uuid4(), user_id="test_user", name="2026 手账本", page_count=0)
    page = Page(
        id=uuid.uuid4(),
        journal_id=old_journal.id,
        user_id="test_user",
        title="跨年归档",
        page_date=date(2026, 7, 1),
    )
    db_session.add_all([old_journal, current_journal, page])
    await db_session.flush()

    updated = await PageService(db_session).update(
        str(page.id),
        "test_user",
        {"journal_id": str(current_journal.id), "page_date": "2026-07-01"},
    )
    await db_session.refresh(old_journal)
    await db_session.refresh(current_journal)

    assert str(updated.journal_id) == str(current_journal.id)
    assert old_journal.page_count == 0
    assert current_journal.page_count == 1

    await PageService(db_session).update(
        str(page.id),
        "test_user",
        {"journal_id": str(current_journal.id), "title": "再次保存"},
    )
    await db_session.refresh(current_journal)

    assert current_journal.page_count == 1
