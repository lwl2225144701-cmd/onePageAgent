import uuid
import pytest
from sqlalchemy import select

from app.models.ai_task import AITask
from app.ai import mcp_client
from app.services.ai_task_service import AITaskService


@pytest.mark.asyncio
async def test_create_ai_task(db_session):
    task = AITask(
        id=uuid.uuid4(), task_id="test_task_001", user_id="test_user",
        status="pending", progress=0,
        input_json={"text": "今天天气真好", "mood": "开心"},
    )
    db_session.add(task)
    await db_session.flush()

    result = (await db_session.execute(select(AITask).where(AITask.task_id == "test_task_001"))).scalar_one()
    assert result.status == "pending"
    assert result.progress == 0
    assert result.input_json["mood"] == "开心"


@pytest.mark.asyncio
async def test_task_status_transitions(db_session):
    task = AITask(
        id=uuid.uuid4(), task_id="test_task_002", user_id="test_user",
        status="pending", progress=0,
        input_json={},
    )
    db_session.add(task)
    await db_session.flush()

    task.status = "processing"
    task.progress = 50
    await db_session.flush()

    result = (await db_session.execute(select(AITask).where(AITask.task_id == "test_task_002"))).scalar_one()
    assert result.status == "processing"
    assert result.progress == 50


@pytest.mark.asyncio
async def test_service_persists_prefetched_journal_context(db_session, monkeypatch):
    async def fake_prepare(input_json, *, task_id):
        return {
            **input_json,
            "page_date": "2026-06-19",
            "journal_context": {
                "source": "journal_mcp",
                "datetime": {"date": "2026-06-19", "timezone": "Asia/Shanghai"},
                "weather": {"text": "晴", "icon": "☀️"},
                "weather_success": True,
                "weather_status": "success",
            },
        }

    monkeypatch.setattr(mcp_client, "prepare_generation_input", fake_prepare)

    task = await AITaskService(db_session).create_task(
        "test_user",
        {"text": "今天很好", "mood": "开心"},
    )

    assert task.input_json["journal_context"]["weather"]["text"] == "晴"
    assert task.input_json["page_date"] == "2026-06-19"
