"""Backfill SVG material previews to use the raw SVG asset URL.

This fixes previously imported builtin SVG materials whose preview_url points to
placeholder PNG previews.
"""
from __future__ import annotations

import asyncio
import mimetypes
from urllib.parse import urlparse

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.minio import get_minio
from app.models.material import Material
from app.services.material_catalog import extract_svg_dimensions


async def backfill_svg_previews() -> None:
    updated = 0
    scanned = 0

    async with async_session_factory() as session:
        materials = (await session.execute(select(Material))).scalars().all()
        for material in materials:
            meta = material.meta_info or {}
            mime_type = str(meta.get("mime_type") or mimetypes.guess_type(str(material.file_url))[0] or "")
            raw_file_url = str(meta.get("raw_file_url") or material.file_url or "").strip()
            preview_url = str(meta.get("preview_url") or "").strip()

            scanned += 1
            next_meta = dict(meta)
            changed = False

            if mime_type and meta.get("mime_type") != mime_type:
                next_meta["mime_type"] = mime_type
                changed = True

            if raw_file_url and meta.get("raw_file_url") != raw_file_url:
                next_meta["raw_file_url"] = raw_file_url
                changed = True

            if mime_type == "image/svg+xml" and raw_file_url and preview_url != raw_file_url:
                next_meta["preview_url"] = raw_file_url
                changed = True

            if mime_type == "image/svg+xml" and raw_file_url and not next_meta.get("aspect_ratio"):
                dimensions = _read_svg_dimensions(raw_file_url)
                if dimensions:
                    width, height = dimensions
                    next_meta["asset_width"] = width
                    next_meta["asset_height"] = height
                    next_meta["aspect_ratio"] = width / height
                    changed = True

            if changed:
                material.meta_info = next_meta
                updated += 1

        await session.commit()

    print({"scanned": scanned, "updated": updated})


def _read_svg_dimensions(raw_file_url: str) -> tuple[float, float] | None:
    object_name = _extract_object_name(raw_file_url)
    if not object_name:
        return None
    obj = get_minio().get_object("onepage-materials", object_name)
    try:
        return extract_svg_dimensions(obj.read())
    finally:
        obj.close()
        obj.release_conn()


def _extract_object_name(url: str) -> str | None:
    path = urlparse(url).path.lstrip("/")
    prefix = "onepage-materials/"
    if not path.startswith(prefix):
        return None
    return path[len(prefix):]


if __name__ == "__main__":
    asyncio.run(backfill_svg_previews())
