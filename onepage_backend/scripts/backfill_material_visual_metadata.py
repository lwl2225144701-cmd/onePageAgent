from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
from uuid import UUID
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageChops
from sqlalchemy import select

from app.ai.gateway.dashscope_vision_client import DashScopeVisionReviewClient, build_image_data_url
from app.ai.layout_v2.schemas import MaterialVisualMetadata, VisualBBox
from app.core.database import async_session_factory
from app.models.material import Material


PROMPT = """分析这张手帐素材图片，只输出 JSON。
字段：subjects、actions、scenes、objects、detected_text、text_heavy、risk_flags、suggested_role、background_safe、visual_style、color_tone、complexity、density。
suggested_role 只能是 background、focal_sticker、supporting_sticker、tape、frame、decoration、none。
risk_flags 仅使用 valentine、wedding、romance、festival_text、medical、sick、wheelchair、elderly_care、religion、business_sales、party。
识别图片中可见的中文、英文和日文；没有文字时 detected_text 为空字符串。"""


async def main() -> None:
    args = parse_args()
    stats = {"success": 0, "skipped": 0, "failed": 0}
    failures: list[dict[str, str]] = []
    async with async_session_factory() as db:
        query = select(Material).order_by(Material.created_at.asc())
        if args.material_id:
            query = query.where(Material.id == UUID(args.material_id))
        materials = list((await db.execute(query)).scalars().all())
        if args.limit:
            materials = materials[: args.limit]

        client = DashScopeVisionReviewClient()
        try:
            for offset in range(0, len(materials), args.batch_size):
                for material in materials[offset : offset + args.batch_size]:
                    meta = dict(material.meta_info or {})
                    if meta.get("manual_override") is True:
                        stats["skipped"] += 1
                        continue
                    if meta.get("annotation_version") == "v2" and not args.force:
                        stats["skipped"] += 1
                        continue
                    try:
                        image_bytes, mime_type = await load_material_image(material)
                        visual_bbox = calculate_visual_bbox(image_bytes, mime_type=mime_type)
                        response = await client.review_contact_sheet(
                            prompt=PROMPT,
                            contact_sheet_data_url=build_image_data_url(image_bytes, mime_type),
                            task_id=f"backfill:{material.id}",
                        )
                        payload = parse_json(response.get("content"))
                        metadata = MaterialVisualMetadata.model_validate(
                            {
                                **payload,
                                "visual_bbox": visual_bbox.model_dump(),
                                "manual_override": False,
                                "annotation_version": "v2",
                            }
                        )
                        if not args.dry_run:
                            material.meta_info = {**meta, **metadata.model_dump(mode="json")}
                            await db.flush()
                        stats["success"] += 1
                    except Exception as exc:
                        stats["failed"] += 1
                        failures.append({"material_id": str(material.id), "error": str(exc)[:240]})
                if not args.dry_run:
                    await db.commit()
        finally:
            await client.close()

    print(json.dumps({**stats, "failures": failures}, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill onePage material visual metadata V2")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--material-id", default="")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.batch_size = max(1, args.batch_size)
    return args


async def load_material_image(material: Material) -> tuple[bytes, str]:
    meta = material.meta_info or {}
    for key in ("origin_path", "target_path"):
        value = str(meta.get(key) or "").strip()
        path = Path(value)
        if value and path.is_file():
            return path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/png"

    for key in ("raw_file_url", "preview_url"):
        url = str(meta.get(key) or "").strip()
        if url.startswith(("http://", "https://")):
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content, response.headers.get("content-type", "image/png").split(";", 1)[0]
    raise RuntimeError("material_image_unavailable")


def calculate_visual_bbox(image_bytes: bytes, *, mime_type: str = "") -> VisualBBox:
    if mime_type.lower().split(";", 1)[0] == "image/svg+xml":
        return VisualBBox()
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    except Exception:
        return VisualBBox()
    width, height = image.size
    alpha = image.getchannel("A")
    alpha_bbox = alpha.point(lambda value: 255 if value > 12 else 0).getbbox()
    if alpha.getextrema()[0] < 255 and alpha_bbox:
        bbox = alpha_bbox
    else:
        rgb = image.convert("RGB")
        difference = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (255, 255, 255))).convert("L")
        bbox = difference.point(lambda value: 255 if value > 18 else 0).getbbox()
    if not bbox:
        return VisualBBox()
    left, top, right, bottom = bbox
    return VisualBBox(
        x=left / width,
        y=top / height,
        w=max(1, right - left) / width,
        h=max(1, bottom - top) / height,
    )


def parse_json(content: Any) -> dict[str, Any]:
    text = str(content or "").strip()
    if "```" in text:
        text = text.replace("```json", "").replace("```", "").strip()
    if "{" in text and "}" in text:
        text = text[text.find("{") : text.rfind("}") + 1]
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("vision_metadata_not_object")
    return payload


if __name__ == "__main__":
    asyncio.run(main())
