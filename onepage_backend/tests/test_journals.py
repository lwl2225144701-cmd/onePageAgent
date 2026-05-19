import pytest
from sqlalchemy import select

from app.models.journal import Journal


@pytest.mark.asyncio
async def test_create_journal(db_session):
    journal = Journal(user_id="test_user_1", name="My Journal")
    db_session.add(journal)
    await db_session.flush()

    result = (await db_session.execute(select(Journal).where(Journal.user_id == "test_user_1"))).scalars().all()
    assert len(result) == 1
    assert result[0].name == "My Journal"
    assert result[0].page_count == 0


@pytest.mark.asyncio
async def test_journal_page_count_default(db_session):
    journal = Journal(user_id="test_user_2", name="Empty Journal")
    db_session.add(journal)
    await db_session.flush()
    assert journal.page_count == 0
