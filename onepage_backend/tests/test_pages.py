import uuid
import pytest
from sqlalchemy import select

from app.models.journal import Journal
from app.models.page import Page
from app.models.element import Element


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
