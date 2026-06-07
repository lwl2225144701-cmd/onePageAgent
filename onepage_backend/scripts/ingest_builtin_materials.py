"""Import builtin materials from the local materials directory into MinIO and DB."""
from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import delete

from app.config import settings
from app.core.minio import get_minio, minio_upload_data
from app.core.database import async_session_factory
from app.models.material import Material
from app.models.material_user_state import MaterialUserState
from app.services.material_catalog import (
    SVG_MIME,
    build_builtin_material_record,
    render_svg_preview,
)

ROOT_DIR = Path(__file__).resolve().parents[2] / "素材" / "materials"
SUPPORTED_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp"}


async def reset_material_library():
    client = get_minio()
    object_names = [item.object_name for item in client.list_objects(settings.MINIO_BUCKET_MATERIALS, recursive=True)]
    for object_name in object_names:
        client.remove_object(settings.MINIO_BUCKET_MATERIALS, object_name)

    async with async_session_factory() as session:
        await session.execute(delete(MaterialUserState))
        await session.execute(delete(Material))
        await session.commit()

    return {"deleted_objects": len(object_names)}


async def seed_builtin_materials(root_dir: Path = ROOT_DIR, *, reset_existing: bool = False):
    batch_id = uuid.uuid4().hex
    scanned = imported = failed = 0
    per_type: dict[str, int] = {}
    per_category: dict[str, int] = {}
    sample_errors: list[str] = []
    reset_summary = {"deleted_objects": 0}

    if reset_existing:
        reset_summary = await reset_material_library()

    async with async_session_factory() as session:
        for file_path in sorted(root_dir.rglob("*")):
            if (
                not file_path.is_file()
                or file_path.name.startswith(".")
                or any(part.startswith(".") for part in file_path.relative_to(root_dir).parts)
                or file_path.suffix.lower() not in SUPPORTED_SUFFIXES
            ):
                continue
            scanned += 1
            try:
                record = build_builtin_material_record(root_dir=root_dir, file_path=file_path)
                file_bytes = file_path.read_bytes()
                ext = file_path.suffix.lower() or ".bin"
                object_key = f"materials/builtin/{record['provider']}/{record['material_type']}/{date.today().year}/{date.today().month:02d}/{uuid.uuid4().hex}{ext}"
                raw_file_url = minio_upload_data(
                    settings.MINIO_BUCKET_MATERIALS,
                    object_key,
                    file_bytes,
                    record["mime_type"],
                    len(file_bytes),
                )

                preview_url = raw_file_url
                preview_bytes = None
                if record["mime_type"] != SVG_MIME:
                    preview_bytes = render_svg_preview(file_bytes, record["display_name"])
                if preview_bytes:
                    preview_key = f"materials/builtin-preview/{record['provider']}/{record['material_type']}/{date.today().year}/{date.today().month:02d}/{uuid.uuid4().hex}.png"
                    preview_url = minio_upload_data(
                        settings.MINIO_BUCKET_MATERIALS,
                        preview_key,
                        preview_bytes,
                        "image/png",
                        len(preview_bytes),
                    )

                material = Material(
                    material_type=record["material_type"],
                    style_tags=record["style_tags"],
                    emotion_tags=record["emotion_tags"],
                    scene_tags=record["scene_tags"],
                    file_url=raw_file_url,
                    meta_info={
                        "source": "builtin_seed",
                        "provider": record["provider"],
                        "origin_path": record["origin_path"],
                        "display_name": record["display_name"],
                        "category": record["category"],
                        "tags": record["tags"],
                        "preview_url": preview_url,
                        "raw_file_url": raw_file_url,
                        "mime_type": record["mime_type"],
                        "asset_width": record.get("asset_width"),
                        "asset_height": record.get("asset_height"),
                        "aspect_ratio": record.get("aspect_ratio"),
                        "visual_style": record.get("visual_style"),
                        "complexity": record.get("complexity"),
                        "density": record.get("density"),
                        "importance": record.get("importance"),
                        "background_safe": record.get("background_safe"),
                        "semantic_blocked": record.get("semantic_blocked"),
                        "visibility": "public",
                        "owner_user_id": None,
                        "ingest_batch_id": batch_id,
                        "metadata": record["metadata"],
                    },
                )
                session.add(material)
                imported += 1
                per_type[record["material_type"]] = per_type.get(record["material_type"], 0) + 1
                per_category[record["category"]] = per_category.get(record["category"], 0) + 1
            except Exception:
                failed += 1
                if len(sample_errors) < 5:
                    import traceback

                    sample_errors.append(f"{file_path}: {traceback.format_exc(limit=1).strip()}")

        await session.commit()

    print(
        {
            "scanned": scanned,
            "imported": imported,
            "failed": failed,
            "per_type": per_type,
            "per_category": per_category,
            "batch_id": batch_id,
            "reset": reset_summary,
            "sample_errors": sample_errors,
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import builtin materials into the onePage material library.")
    parser.add_argument("--root", type=Path, default=ROOT_DIR, help="Local materials root directory.")
    parser.add_argument("--reset", action="store_true", help="Delete all material DB rows and onepage-materials objects before import.")
    args = parser.parse_args()
    asyncio.run(seed_builtin_materials(args.root, reset_existing=args.reset))
