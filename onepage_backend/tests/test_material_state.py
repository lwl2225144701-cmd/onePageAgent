import pytest

from app.services.material_service import MaterialService
from app.models.material import Material


@pytest.mark.asyncio
async def test_material_favorite_and_recent_state(db_session):
    material = Material(
        material_type="sticker",
        file_url="http://127.0.0.1:9000/onepage-materials/test.png",
        meta_info={"visibility": "private", "owner_user_id": "test_user", "category": "开心", "tags": ["小狗"]},
    )
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)

    svc = MaterialService(db_session)

    favorited = await svc.set_favorite(material_id=str(material.id), user_id="test_user", is_favorite=True)
    assert getattr(favorited, "_user_state").is_favorite is True

    used = await svc.mark_used(material_id=str(material.id), user_id="test_user")
    assert getattr(used, "_user_state").last_used_at is not None

    favorites, favorite_total = await svc.list_favorites(user_id="test_user")
    recents, recent_total = await svc.list_recent(user_id="test_user")

    assert favorite_total == 1
    assert recent_total == 1
    assert str(favorites[0].id) == str(material.id)
    assert str(recents[0].id) == str(material.id)


@pytest.mark.asyncio
async def test_mark_used_by_layout_urls(db_session):
    material = Material(
        material_type="sticker",
        file_url="http://127.0.0.1:9000/onepage-materials/layout-used.png",
        meta_info={"visibility": "private", "owner_user_id": "test_user", "category": "开心", "tags": ["花朵"]},
    )
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)

    svc = MaterialService(db_session)
    used_count = await svc.mark_used_by_urls(
        user_id="test_user",
        urls=svc.extract_material_urls_from_layout(
            {
                "elements": [
                    {"type": "sticker", "props": {"url": material.file_url}},
                    {"type": "text", "props": {"content": "hello"}},
                ]
            }
        ),
    )
    await db_session.commit()

    recents, total = await svc.list_recent(user_id="test_user")
    assert used_count == 1
    assert total == 1
    assert str(recents[0].id) == str(material.id)


@pytest.mark.asyncio
async def test_mark_used_by_proxy_urls(db_session):
    material = Material(
        material_type="sticker",
        file_url="http://127.0.0.1:9000/onepage-materials/proxy-used.png",
        meta_info={"visibility": "private", "owner_user_id": "test_user", "category": "开心", "tags": ["花朵"]},
    )
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)

    svc = MaterialService(db_session)
    proxy_url = svc.build_material_proxy_url(material, "asset", "test_user")
    used_count = await svc.mark_used_by_urls(user_id="test_user", urls=[proxy_url])
    await db_session.commit()

    recents, total = await svc.list_recent(user_id="test_user")
    assert used_count == 1
    assert total == 1
    assert str(recents[0].id) == str(material.id)
