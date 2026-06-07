import uuid
import pytest
from sqlalchemy import select

from app.ai.pipeline import step4_material
from app.ai.pipeline.step4_material import annotate_layout_suggestions, run_material_matching, summarize_recall_candidates
from app.models.material import Material
from app.services.material_service import MaterialService


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


def test_derive_material_tags_for_uploaded_assets():
    style_tags, emotion_tags, scene_tags = MaterialService.derive_material_tags(
        "sticker",
        "人物场景",
        ["插画", "旅行", "治愈"],
    )

    assert "插画" in style_tags
    assert "治愈" in emotion_tags
    assert "旅行" in scene_tags


@pytest.mark.asyncio
async def test_retrieve_layout_candidates_uses_meta_info_and_visibility(db_session):
    own_material = Material(
        id=uuid.uuid4(),
        material_type="sticker",
        style_tags=[],
        emotion_tags=[],
        scene_tags=[],
        file_url="/own.png",
        meta_info={
            "owner_user_id": "user-a",
            "visibility": "private",
            "category": "开心",
            "tags": ["小熊", "旅行"],
        },
    )
    other_private = Material(
        id=uuid.uuid4(),
        material_type="sticker",
        style_tags=[],
        emotion_tags=[],
        scene_tags=[],
        file_url="/other.png",
        meta_info={
            "owner_user_id": "user-b",
            "visibility": "private",
            "category": "开心",
            "tags": ["小熊"],
        },
    )
    db_session.add_all([own_material, other_private])
    await db_session.flush()

    svc = MaterialService(db_session)
    result = await svc.retrieve_layout_candidates(
        user_id="user-a",
        emotion="开心",
        scene="旅行",
        style="小熊",
        weather="晴",
        keywords=["旅行", "小熊"],
    )

    assert len(result["groups"]) == 1
    first_group = result["groups"][0]
    assert first_group["material_type"] == "sticker"
    assert len(first_group["items"]) == 1
    assert f"/api/materials/{own_material.id}/asset?anonymous_user_id=user-a" in first_group["items"][0]["file_url"]
    assert first_group["items"][0]["raw_file_url"] == "/own.png"
    assert "emotion:开心" in first_group["items"][0]["match_reasons"]
    assert "scene:旅行" in first_group["items"][0]["match_reasons"]


@pytest.mark.asyncio
async def test_retrieve_layout_candidates_prioritizes_favorite_and_recent(db_session):
    favorite_material = Material(
        id=uuid.uuid4(),
        material_type="sticker",
        style_tags=[],
        emotion_tags=[],
        scene_tags=[],
        file_url="/favorite.png",
        meta_info={
            "owner_user_id": "user-a",
            "visibility": "private",
            "category": "开心",
            "tags": ["小熊"],
        },
    )
    plain_material = Material(
        id=uuid.uuid4(),
        material_type="sticker",
        style_tags=[],
        emotion_tags=[],
        scene_tags=[],
        file_url="/plain.png",
        meta_info={
            "owner_user_id": "user-a",
            "visibility": "private",
            "category": "开心",
            "tags": ["小熊"],
        },
    )
    db_session.add_all([favorite_material, plain_material])
    await db_session.commit()
    await db_session.refresh(favorite_material)

    svc = MaterialService(db_session)
    await svc.set_favorite(material_id=str(favorite_material.id), user_id="user-a", is_favorite=True)
    await svc.mark_used(material_id=str(favorite_material.id), user_id="user-a")

    result = await svc.retrieve_layout_candidates(
        user_id="user-a",
        emotion="开心",
        scene="",
        style="小熊",
        weather="",
        keywords=["小熊"],
    )

    first_item = result["groups"][0]["items"][0]
    assert f"/api/materials/{favorite_material.id}/asset?anonymous_user_id=user-a" in first_item["file_url"]
    assert "preference:favorite" in first_item["match_reasons"]
    assert "preference:recent" in first_item["match_reasons"]


@pytest.mark.asyncio
async def test_retrieve_layout_candidates_expands_emotion_to_content_categories(db_session):
    calm_background = Material(
        id=uuid.uuid4(),
        material_type="background",
        style_tags=[],
        emotion_tags=[],
        scene_tags=[],
        file_url="/paper.svg",
        meta_info={"visibility": "public", "category": "纸张纹理", "tags": ["paper"]},
    )
    flower_sticker = Material(
        id=uuid.uuid4(),
        material_type="sticker",
        style_tags=[],
        emotion_tags=[],
        scene_tags=[],
        file_url="/flower.svg",
        meta_info={"visibility": "public", "category": "花草", "tags": ["flower"]},
    )
    db_session.add_all([calm_background, flower_sticker])
    await db_session.flush()

    svc = MaterialService(db_session)
    result = await svc.retrieve_layout_candidates(
        user_id="user-a",
        emotion="calm",
        scene="",
        style="",
        weather="",
        keywords=[],
    )

    grouped = {group["material_type"]: group["items"] for group in result["groups"]}
    assert grouped["background"][0]["category"] == "纸张纹理"
    assert grouped["sticker"][0]["category"] == "花草"
    assert any(reason.startswith("emotion:") for reason in grouped["background"][0]["match_reasons"])


@pytest.mark.asyncio
async def test_retrieve_layout_candidates_expands_scene_keywords(db_session):
    coffee_scene = Material(
        id=uuid.uuid4(),
        material_type="sticker",
        style_tags=["插画"],
        emotion_tags=[],
        scene_tags=["咖啡"],
        file_url="/coffee.svg",
        meta_info={"visibility": "public", "category": "人物场景", "tags": ["coffee"]},
    )
    db_session.add(coffee_scene)
    await db_session.flush()

    svc = MaterialService(db_session)
    result = await svc.retrieve_layout_candidates(
        user_id="user-a",
        emotion="healing",
        scene="coffee",
        style="illustration",
        weather="",
        keywords=["coffee"],
    )

    first = result["groups"][0]["items"][0]
    assert first["category"] == "人物场景"
    assert "scene:coffee" in first["match_reasons"]
    assert "keyword:咖啡" in first["match_reasons"]


@pytest.mark.asyncio
async def test_retrieve_layout_candidates_prefers_safe_low_density_background(db_session):
    safe_background = Material(
        id=uuid.uuid4(),
        material_type="background",
        style_tags=[],
        emotion_tags=[],
        scene_tags=["家庭"],
        file_url="/paper.svg",
        meta_info={
            "visibility": "public",
            "category": "纸张纹理",
            "tags": ["warm cream paper texture"],
            "density": "low",
            "complexity": "low",
            "background_safe": True,
            "importance": "background",
            "visual_style": "paper",
        },
    )
    busy_background = Material(
        id=uuid.uuid4(),
        material_type="background",
        style_tags=[],
        emotion_tags=[],
        scene_tags=["家庭"],
        file_url="/busy.svg",
        meta_info={
            "visibility": "public",
            "category": "海边",
            "tags": ["winding floral line pattern"],
            "density": "high",
            "complexity": "high",
            "background_safe": False,
            "importance": "background_candidate",
            "visual_style": "texture",
        },
    )
    db_session.add_all([busy_background, safe_background])
    await db_session.flush()

    svc = MaterialService(db_session)
    result = await svc.retrieve_layout_candidates(
        user_id="user-a",
        emotion="开心",
        scene="家庭",
        style="warm",
        weather="",
        keywords=["饺子", "家庭"],
    )

    grouped = {group["material_type"]: group["items"] for group in result["groups"]}
    assert f"/api/materials/{safe_background.id}/asset?anonymous_user_id=user-a" in grouped["background"][0]["file_url"]
    assert "quality:background_safe" in grouped["background"][0]["match_reasons"]


def test_summarize_recall_candidates_reports_counts():
    summary = summarize_recall_candidates(
        {
            "groups": [
                {
                    "material_type": "sticker",
                    "items": [
                        {
                            "material_id": "a",
                            "display_name": "A",
                            "origin_path": "a.svg",
                            "category": "开心",
                            "aspect_ratio": 1.2,
                            "score": 8,
                            "match_reasons": ["emotion:开心"],
                        }
                    ],
                },
                {
                    "material_type": "background",
                    "items": [
                        {
                            "material_id": "b",
                            "display_name": "B",
                            "origin_path": "b.svg",
                            "category": "纸张纹理",
                            "aspect_ratio": 1.0,
                            "score": 6,
                            "match_reasons": ["scene:咖啡"],
                        }
                    ],
                },
            ]
        }
    )

    assert summary["total_candidates"] == 2
    assert summary["group_counts"] == {"sticker": 1, "background": 1}
    assert summary["recalled_materials"]["sticker"][0]["display_name"] == "A"


def test_annotate_layout_suggestions_sets_background_preference_and_roles():
    candidates = {
        "summary": {"emotion": "治愈", "scene": "咖啡"},
        "groups": [
            {"material_type": "background", "items": [{"material_id": "bg-1", "display_name": "paper", "file_url": "/bg.svg", "preview_url": "/bg-preview.svg", "category": "纸张纹理"}]},
            {"material_type": "sticker", "items": [{"material_id": "st-1", "display_name": "coffee", "file_url": "/st.svg", "preview_url": "/st-preview.svg", "category": "人物场景"}]},
            {"material_type": "decoration", "items": [{"material_id": "de-1", "display_name": "ribbon", "file_url": "/de.svg", "preview_url": "/de-preview.svg", "category": "丝带"}]},
        ],
    }

    annotate_layout_suggestions(candidates, emotion="治愈", scene="咖啡", style="healing")

    summary = candidates["summary"]["layout_guidance"]
    assert summary["background_strategy"] == "material_background"
    assert summary["preferred_background"]["material_id"] == "bg-1"
    assert candidates["groups"][0]["items"][0]["suggested_role"] == "background"
    assert candidates["groups"][1]["items"][0]["suggested_role"] == "focal_sticker"
    assert candidates["groups"][2]["items"][0]["suggested_role"] == "decoration"


@pytest.mark.asyncio
async def test_run_material_matching_retries_after_candidate_failure(monkeypatch):
    calls = {"retrieve": 0, "dispose": 0}

    async def fake_retrieve_candidates(**_kwargs):
        calls["retrieve"] += 1
        if calls["retrieve"] == 1:
            raise RuntimeError("connection closed")
        return {
            "summary": {},
            "groups": [
                {
                    "material_type": "background",
                    "items": [{"material_id": "bg-1", "display_name": "paper", "file_url": "/bg.svg", "preview_url": "/bg.svg", "category": "纸张纹理"}],
                }
            ],
        }

    async def fake_dispose_db_engine():
        calls["dispose"] += 1

    monkeypatch.setattr(step4_material, "retrieve_candidates", fake_retrieve_candidates)
    monkeypatch.setattr(step4_material, "dispose_db_engine", fake_dispose_db_engine)

    result = await run_material_matching(
        {
            "task_id": "task-1",
            "user_id": "user-1",
            "step1": {"text_analysis": {"scene": "阅读"}},
            "step2": {"primary_emotion": "calm", "keywords": ["书"]},
            "step3": {"theme": "healing"},
            "input_json": {"text": "今天在书店读书", "mood": "平静", "weather": {"weather": "晴"}},
        }
    )

    assert calls == {"retrieve": 2, "dispose": 1}
    assert result["groups"][0]["items"][0]["suggested_role"] == "background"
