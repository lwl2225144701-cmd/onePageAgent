import uuid
import pytest
from sqlalchemy import select

from app.models.ai_task import AITask
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
async def test_service_persists_request_environment_without_prefetch(db_session):
    environment = {
        "date": "2026-06-20",
        "time": "14:35",
        "weekday": "周六",
        "city": "深圳市",
        "district": "福田区",
        "weather": "多云",
        "temperature": 29,
        "icon_key": "cloudy",
        "source": "amap",
    }
    task = await AITaskService(db_session).create_task(
        "test_user",
        {"text": "今天很好", "mood": "开心", "environment_context": environment},
    )

    assert task.input_json["environment_context"] == environment
    assert "journal_context" not in task.input_json
