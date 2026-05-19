import uuid
import pytest
from sqlalchemy import select

from app.models.material import Material


@pytest.mark.asyncio
async def test_create_material(db_session):
    material = Material(
        id=uuid.uuid4(), material_type="sticker",
        style_tags=["healing", "cute"], emotion_tags=["happy"],
        scene_tags=["daily"], file_url="/test/sticker.png",
    )
    db_session.add(material)
    await db_session.flush()

    result = (await db_session.execute(select(Material).where(Material.material_type == "sticker"))).scalars().all()
    assert len(result) == 1
    assert "healing" in result[0].style_tags


@pytest.mark.asyncio
async def test_filter_by_emotion(db_session):
    m1 = Material(id=uuid.uuid4(), material_type="sticker", emotion_tags=["happy"], file_url="/t1.png")
    m2 = Material(id=uuid.uuid4(), material_type="sticker", emotion_tags=["sad"], file_url="/t2.png")
    db_session.add_all([m1, m2])
    await db_session.flush()

    # Filter by happy (Python-side filtering for JSON columns)
    all_materials = (await db_session.execute(select(Material))).scalars().all()
    happy_materials = [m for m in all_materials if m.emotion_tags and "happy" in m.emotion_tags]
    assert len(happy_materials) == 1
    assert happy_materials[0].emotion_tags == ["happy"]
