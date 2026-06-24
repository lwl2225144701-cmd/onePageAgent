import pytest

from app.ai.pipeline import step1_content
from app.ai.layout_v2.visual_brief import build_visual_brief
from app.ai.pipeline.step1_content import normalize_unified_analysis
from app.ai.prompt_registry import build_unified_analysis_prompt


def test_unified_analysis_normalizes_semantic_sentiment_and_style():
    result = normalize_unified_analysis(
        {
            "semantic": {
                "topic": "桂林米粉小记",
                "scene": "food",
                "sub_scene": "food_review",
                "intent": "food_record",
                "primary_subject": "桂林米粉",
                "objects": ["桂林米粉", "米粉店"],
                "keywords": ["桂林米粉", "米粉", "主食"],
                "required_concepts": ["food", "noodle"],
                "avoid_tags": ["party", "wedding"],
                "title_hint": "热乎乎的快乐",
            },
            "sentiment": {"primary_emotion": "happy", "confidence": 0.92},
            "style": {
                "theme": "warm",
                "font": "handwriting",
                "color_palette": ["#FAF6F0", "#C4A882", "#5C4A3A"],
                "layout_style": "diary",
                "preferred_density": "medium",
                "preferred_color_tone": ["warm", "soft"],
            },
        },
        user_text="今天吃了桂林米粉",
        user_mood="开心",
    )

    assert result["semantic"]["scene"] == "food"
    assert result["semantic"]["objects"] == ["桂林米粉", "米粉店"]
    assert result["sentiment"]["primary_emotion"] == "happy"
    assert result["style"]["theme"] == "warm"
    assert "party" in result["semantic"]["excluded_concepts"]


def test_visual_brief_trusts_ai_semantics_instead_of_scanning_text_keywords():
    brief = build_visual_brief(
        text="文中顺带提到昨天吃过饺子，但今天主要复习考试",
        mood="平静",
        semantic={
            "scene": "study",
            "sub_scene": "study_reflection",
            "primary_subject": "复习资料",
            "objects": ["笔记", "试卷"],
            "required_concepts": ["study", "exam"],
            "visual_keywords": ["学习", "复习", "笔记"],
            "title_hint": "认真复习的一天",
        },
    )

    assert brief.scene == "study"
    assert brief.sub_scene == "study_reflection"
    assert brief.objects == ["笔记", "试卷"]
    assert "food" not in brief.required_concepts


def test_unified_prompt_requests_retrieval_ready_keywords_without_sql():
    prompt = build_unified_analysis_prompt(
        user_text="今天吃了桂林米粉",
        mood="开心",
        environment_context={"weather": "多云"},
        user_preferences={"theme": "healing"},
    )

    assert "required_concepts" in prompt
    assert "visual_keywords" in prompt
    assert "桂林米粉" in prompt
    assert "SQL" not in prompt


@pytest.mark.asyncio
async def test_content_understanding_uses_one_unified_model_call(monkeypatch):
    calls = []

    async def fake_run_json_llm_step(**kwargs):
        calls.append(kwargs)
        return {
            "semantic": {
                "topic": "桂林米粉小记",
                "scene": "food",
                "sub_scene": "food_review",
                "intent": "food_record",
                "objects": ["桂林米粉"],
                "keywords": ["桂林米粉", "米粉"],
                "visual_keywords": ["主食料理"],
                "required_concepts": ["food", "noodle"],
                "title_hint": "热乎乎的快乐",
            },
            "sentiment": {"primary_emotion": "happy", "confidence": 0.9},
            "style": {"theme": "warm", "font": "handwriting", "layout_style": "diary"},
        }

    monkeypatch.setattr(step1_content, "run_json_llm_step", fake_run_json_llm_step)
    result = await step1_content.run_content_understanding(
        {
            "task_id": "unified-test",
            "input_json": {
                "text": "今天吃了桂林米粉",
                "mood": "开心",
                "environment_context": {"weather": "多云"},
            },
        }
    )

    assert len(calls) == 1
    assert result["scene"] == "food"
    assert result["sentiment"]["primary_emotion"] == "happy"
    assert result["style"]["theme"] == "warm"
