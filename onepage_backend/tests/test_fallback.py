import json

from app.ai.fallback.templates import get_fallback_layout
from app.ai.fallback.validator import LayoutValidator
from app.ai.fallback.repairer import LayoutRepairer


def test_get_fallback_layout():
    layout = get_fallback_layout("happy")
    assert "page" in layout
    assert "elements" in layout
    assert "style" in layout
    assert layout["page"]["width"] == 1080
    assert layout["style"]["theme"] == "warm"


def test_get_default_layout():
    layout = get_fallback_layout("nonexistent")
    assert layout["style"]["theme"] == "healing"


def test_validator_valid_layout():
    validator = LayoutValidator()
    layout = get_fallback_layout("neutral")
    errors = validator.validate(layout)
    assert len(errors) == 0


def test_validator_invalid_layout():
    validator = LayoutValidator()
    errors = validator.validate({})
    assert len(errors) > 0


def test_repairer_missing_fields():
    repairer = LayoutRepairer()
    repaired = repairer.repair('{"style": {}}', [])
    assert repaired is not None
    assert "page" in repaired
    assert "elements" in repaired
    assert repaired["page"]["width"] == 1080
    assert repaired["style"]["theme"] == "healing"


def test_repairer_trailing_commas():
    repairer = LayoutRepairer()
    repaired = repairer.repair('{"page": {"width": 1080,}, "elements": [], "style": {"theme": "healing", "font": "handwriting",},}', [])
    assert repaired is not None
    assert repaired["page"]["width"] == 1080


def test_repairer_extract_from_markdown():
    repairer = LayoutRepairer()
    raw = '```json\n{"page": {"width": 1080, "height": 1920, "background": "#FAF6F0"}, "elements": [], "style": {"theme": "healing", "font": "handwriting"}}\n```'
    repaired = repairer.repair(raw, [])
    assert repaired is not None
    assert repaired["page"]["width"] == 1080


def test_full_fallback_pipeline():
    """Test the complete validation/repair/fallback loop."""
    validator = LayoutValidator()
    repairer = LayoutRepairer()

    emotion = "neutral"
    fallback = get_fallback_layout(emotion)

    errors = validator.validate(fallback)
    assert len(errors) == 0, f"Fallback template has errors: {errors}"

    # Simulate repair of fallback
    repaired = repairer.repair(json.dumps(fallback, ensure_ascii=False), [])
    assert repaired is not None
    assert repaired["page"]["width"] == 1080
