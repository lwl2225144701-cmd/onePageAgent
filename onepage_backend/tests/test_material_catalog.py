from pathlib import Path

from app.services.material_catalog import (
    build_builtin_material_record,
    extract_svg_metadata,
    infer_quality_profile,
    infer_category,
    infer_material_type,
    render_placeholder_preview,
)


def test_extract_svg_metadata_reads_title_and_docname(tmp_path: Path):
    file_path = tmp_path / "flower.svg"
    file_path.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" sodipodi:docname="Wild Flower.svg"><title>Flower</title></svg>""",
        encoding="utf-8",
    )

    metadata = extract_svg_metadata(file_path)

    assert metadata["title"] == "Flower"
    assert metadata["docname"] == "Wild Flower.svg"


def test_build_builtin_material_record_maps_directory_and_metadata(tmp_path: Path):
    root_dir = tmp_path / "materials"
    file_path = root_dir / "openclipart" / "flower" / "demo.svg"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><title>Demo Flower</title></svg>', encoding="utf-8")

    record = build_builtin_material_record(root_dir=root_dir, file_path=file_path)

    assert record["provider"] == "openclipart"
    assert record["material_type"] == "sticker"
    assert record["category"] == "花草"
    assert "flower" in record["tags"]
    assert "可爱" not in (record["style_tags"] or [])


def test_infer_material_type_for_opendoodles_defaults_to_sticker():
    assert infer_material_type("opendoodles", "anything") == "sticker"


def test_infer_background_category_prefers_keyword_match():
    category = infer_category(material_type="background", directory_name="background", keywords=["misty blue ocean texture"])

    assert category == "海边"


def test_build_builtin_material_record_maps_clipsafari_frame_to_decoration(tmp_path: Path):
    root_dir = tmp_path / "materials"
    file_path = root_dir / "clipsafari" / "frame" / "frame_01.svg"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><title>Vintage Frame</title></svg>', encoding="utf-8")

    record = build_builtin_material_record(root_dir=root_dir, file_path=file_path)

    assert record["material_type"] == "decoration"
    assert record["category"] == "框架"
    assert "装饰" in record["style_tags"]


def test_build_builtin_material_record_maps_opendoodles_to_people_scene(tmp_path: Path):
    root_dir = tmp_path / "materials"
    file_path = root_dir / "opendoodles" / "composition-01.svg"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><title>Family Scene</title></svg>', encoding="utf-8")

    record = build_builtin_material_record(root_dir=root_dir, file_path=file_path)

    assert record["material_type"] == "sticker"
    assert record["category"] == "人物场景"
    assert "illustration" in record["tags"]
    assert "插画" in record["style_tags"]


def test_build_builtin_material_record_maps_flat_opendoodles_file_to_people_scene(tmp_path: Path):
    root_dir = tmp_path / "materials"
    file_path = root_dir / "opendoodles" / "coffee.svg"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")

    record = build_builtin_material_record(root_dir=root_dir, file_path=file_path)

    assert record["material_type"] == "sticker"
    assert record["category"] == "人物场景"
    assert "咖啡" in record["scene_tags"]


def test_build_builtin_material_record_maps_new_clipsafari_dirs(tmp_path: Path):
    root_dir = tmp_path / "materials"
    file_path = root_dir / "clipsafari" / "dog" / "dog_01.svg"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")

    record = build_builtin_material_record(root_dir=root_dir, file_path=file_path)

    assert record["material_type"] == "sticker"
    assert record["category"] == "动物"


def test_render_placeholder_preview_returns_png_bytes():
    data = render_placeholder_preview("Flower")

    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_infer_quality_profile_marks_busy_background_unsafe():
    profile = infer_quality_profile(
        material_type="background",
        category="海边",
        provider="openclipart",
        directory_name="background",
        keywords=["winding floral line pattern"],
    )

    assert profile["density"] == "high"
    assert profile["background_safe"] is False


def test_infer_quality_profile_marks_paper_background_safe():
    profile = infer_quality_profile(
        material_type="background",
        category="纸张纹理",
        provider="openclipart",
        directory_name="background",
        keywords=["warm cream paper texture"],
    )

    assert profile["density"] == "low"
    assert profile["background_safe"] is True
