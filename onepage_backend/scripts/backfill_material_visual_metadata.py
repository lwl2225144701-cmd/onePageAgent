from __future__ import annotations

import argparse
import asyncio
import json
import math
import mimetypes
from uuid import UUID
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageChops, ImageDraw, ImageOps
from sqlalchemy import select

from app.ai.gateway.dashscope_vision_client import DashScopeVisionReviewClient, build_image_data_url
from app.ai.layout_v2.schemas import MaterialVisualMetadata, VisualBBox
from app.core.database import async_session_factory
from app.models.material import Material


ROLE_VALUES = {"background", "focal_sticker", "supporting_sticker", "tape", "frame", "decoration", "none"}
RISK_VALUES = {
    "valentine",
    "wedding",
    "romance",
    "festival_text",
    "medical",
    "sick",
    "wheelchair",
    "elderly_care",
    "religion",
    "business_sales",
    "party",
}


async def main() -> None:
    args = parse_args()
    stats = {"success": 0, "skipped": 0, "failed": 0}
    failures: list[dict[str, str]] = []
    async with async_session_factory() as db:
        query = select(Material).order_by(Material.created_at.asc())
        if args.material_id:
            query = query.where(Material.id == UUID(args.material_id))
        all_materials = list((await db.execute(query)).scalars().all())
        materials: list[Material] = []
        for material in all_materials:
            meta = dict(material.meta_info or {})
            if meta.get("manual_override") is True or (meta.get("annotation_version") == "v2" and not args.force):
                stats["skipped"] += 1
                continue
            materials.append(material)
        if args.limit:
            materials = materials[: args.limit]

        http_client = httpx.AsyncClient(timeout=30)
        try:
            batches = [
                (offset, materials[offset : offset + args.batch_size])
                for offset in range(0, len(materials), args.batch_size)
            ]
            for wave_start in range(0, len(batches), args.concurrency):
                wave = batches[wave_start : wave_start + args.concurrency]
                results = await asyncio.gather(
                    *[
                        review_material_batch(
                            batch=batch,
                            offset=offset,
                            http_client=http_client,
                        )
                        for offset, batch in wave
                    ]
                )
                for result in results:
                    failures.extend(result["failures"])
                    stats["failed"] += len(result["failures"])
                    for material, metadata in result["updates"]:
                        if not args.dry_run:
                            meta = dict(material.meta_info or {})
                            material.meta_info = {**meta, **metadata.model_dump(mode="json")}
                            await db.flush()
                        stats["success"] += 1
                if not args.dry_run:
                    await db.commit()
                processed = min(sum(len(batch) for _, batch in batches[: wave_start + len(wave)]), len(materials))
                print(
                    "MATERIAL_V2_BACKFILL_PROGRESS "
                    f"processed={processed} total={len(materials)} "
                    f"success={stats['success']} failed={stats['failed']} skipped={stats['skipped']}",
                    flush=True,
                )
        finally:
            await http_client.aclose()

    print(json.dumps({**stats, "failures": failures}, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill onePage material visual metadata V2")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--material-id", default="")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.batch_size = min(32, max(1, args.batch_size))
    args.concurrency = min(8, max(1, args.concurrency))
    return args


async def review_material_batch(
    *,
    batch: list[Material],
    offset: int,
    http_client: httpx.AsyncClient,
) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    updates: list[tuple[Material, MaterialVisualMetadata]] = []
    prepared_results = await asyncio.gather(
        *[
            prepare_material(material, label=f"A{index:02d}", http_client=http_client)
            for index, material in enumerate(batch, start=1)
        ],
        return_exceptions=True,
    )
    prepared: list[dict[str, Any]] = []
    for material, result in zip(batch, prepared_results, strict=True):
        if isinstance(result, BaseException):
            failures.append({"material_id": str(material.id), "error": str(result)[:240]})
        else:
            prepared.append(result)
    if not prepared:
        return {"updates": updates, "failures": failures}

    client = DashScopeVisionReviewClient()
    try:
        sheet_bytes = build_contact_sheet(prepared)
        response = await client.review_contact_sheet(
            prompt=build_prompt(prepared),
            contact_sheet_data_url=build_image_data_url(sheet_bytes, "image/jpeg"),
            task_id=f"backfill:{offset + 1}-{offset + len(batch)}",
        )
        payload_by_label = parse_batch_json(response.get("content"))
    except Exception as exc:
        failures.extend(
            {"material_id": str(item["material"].id), "error": str(exc)[:240]}
            for item in prepared
        )
        return {"updates": updates, "failures": failures}
    finally:
        await client.close()

    for item in prepared:
        material = item["material"]
        payload = payload_by_label.get(item["label"])
        if payload is None:
            failures.append({"material_id": str(material.id), "error": "vision_result_missing_label"})
            continue
        try:
            metadata = MaterialVisualMetadata.model_validate(
                {
                    **normalize_visual_payload(payload),
                    "visual_bbox": item["visual_bbox"].model_dump(),
                    "manual_override": False,
                    "annotation_version": "v2",
                }
            )
            updates.append((material, metadata))
        except Exception as exc:
            failures.append({"material_id": str(material.id), "error": str(exc)[:240]})
    return {"updates": updates, "failures": failures}


async def prepare_material(material: Material, *, label: str, http_client: httpx.AsyncClient) -> dict[str, Any]:
    image_bytes, mime_type = await load_material_image(material, http_client=http_client)
    image = decode_image(image_bytes)
    image.thumbnail((200, 160), Image.Resampling.LANCZOS)
    return {
        "label": label,
        "material": material,
        "image_bytes": image_bytes,
        "mime_type": mime_type,
        "thumbnail": image,
        "visual_bbox": calculate_visual_bbox(image_bytes, mime_type=mime_type),
    }


async def load_material_image(material: Material, *, http_client: httpx.AsyncClient | None = None) -> tuple[bytes, str]:
    meta = material.meta_info or {}
    for key in ("origin_path", "target_path"):
        value = str(meta.get(key) or "").strip()
        path = Path(value)
        if value and path.is_file():
            image_bytes = path.read_bytes()
            if is_decodable_image(image_bytes):
                return image_bytes, mimetypes.guess_type(path.name)[0] or "image/png"

    errors: list[str] = []
    for key in ("raw_file_url", "preview_url"):
        url = str(meta.get(key) or "").strip()
        if url.startswith(("http://", "https://")):
            if http_client is None:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(url)
            else:
                response = await http_client.get(url)
            try:
                response.raise_for_status()
            except Exception as exc:
                errors.append(f"{key}:{exc}")
                continue
            if is_decodable_image(response.content):
                return response.content, response.headers.get("content-type", "image/png").split(";", 1)[0]
            errors.append(f"{key}:invalid_image_response")
    raise RuntimeError("material_image_unavailable:" + ";".join(errors))


def build_contact_sheet(prepared: list[dict[str, Any]]) -> bytes:
    thumb_width, thumb_height, label_height = 220, 180, 34
    columns = min(4, max(1, math.ceil(math.sqrt(len(prepared)))))
    rows = math.ceil(len(prepared) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), (248, 245, 238))
    for index, item in enumerate(prepared):
        image = item["thumbnail"]
        tile = Image.new("RGBA", (thumb_width, thumb_height), (250, 246, 239, 255))
        tile.alpha_composite(image, ((thumb_width - image.width) // 2, (thumb_height - image.height) // 2))
        x = (index % columns) * thumb_width
        y = (index // columns) * (thumb_height + label_height)
        sheet.paste(tile.convert("RGB"), (x, y))
        draw = ImageDraw.Draw(sheet)
        draw.rounded_rectangle((x + 8, y + 8, x + 62, y + 34), radius=9, fill=(226, 197, 151))
        draw.text((x + 18, y + 13), item["label"], fill=(79, 61, 44))
    buffer = BytesIO()
    sheet.save(buffer, format="JPEG", quality=82, optimize=True)
    return buffer.getvalue()


def decode_image(image_bytes: bytes) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGBA")


def is_decodable_image(image_bytes: bytes) -> bool:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
        return True
    except Exception:
        return False


def build_prompt(prepared: list[dict[str, Any]]) -> str:
    items = []
    for item in prepared:
        material = item["material"]
        meta = dict(material.meta_info or {})
        items.append(
            {
                "label": item["label"],
                "filename": meta.get("filename") or meta.get("display_name") or "",
                "material_type": str(material.material_type or ""),
                "category": meta.get("category") or "",
            }
        )
    return (
        "分析这张手帐素材编号宫格，只输出 JSON，不要 Markdown。每个编号必须且只能返回一条。\n"
        "字段：label、subjects、actions、scenes、objects、detected_text、text_heavy、risk_flags、suggested_role、background_safe、visual_style、color_tone、complexity、density。\n"
        "complexity 和 density 只能是 low、medium、high。suggested_role 只能是 background、focal_sticker、supporting_sticker、tape、frame、decoration、none。\n"
        "risk_flags 只能使用 valentine、wedding、romance、festival_text、medical、sick、wheelchair、elderly_care、religion、business_sales、party。\n"
        "识别可见中文、英文和日文；没有文字时 detected_text 为空字符串。\n"
        f"素材编号：{json.dumps(items, ensure_ascii=False)}\n"
        "输出格式：{\"items\":[{\"label\":\"A01\",\"subjects\":[],\"actions\":[],\"scenes\":[],\"objects\":[],\"detected_text\":\"\",\"text_heavy\":false,\"risk_flags\":[],\"suggested_role\":\"decoration\",\"background_safe\":false,\"visual_style\":\"\",\"color_tone\":\"\",\"complexity\":\"low\",\"density\":\"low\"}]}"
    )


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


def parse_batch_json(content: Any) -> dict[str, dict[str, Any]]:
    text = str(content or "").strip()
    if "```" in text:
        text = text.replace("```json", "").replace("```", "").strip()
    if "{" in text and "}" in text:
        text = text[text.find("{") : text.rfind("}") + 1]
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("vision_metadata_not_object")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raw_items = [payload]
    result: dict[str, dict[str, Any]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip().upper()
        if label:
            result[label] = item
    if not result:
        raise ValueError("vision_metadata_items_missing")
    return result


def normalize_visual_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["complexity"] = normalize_density(payload.get("complexity"))
    result["density"] = normalize_density(payload.get("density"))
    result["text_heavy"] = normalize_bool(payload.get("text_heavy"))
    result["background_safe"] = normalize_bool(payload.get("background_safe"))
    result["suggested_role"] = normalize_role(payload.get("suggested_role"))
    risks = payload.get("risk_flags") if isinstance(payload.get("risk_flags"), list) else []
    result["risk_flags"] = [str(item).strip() for item in risks if str(item).strip() in RISK_VALUES]
    return result


def normalize_density(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"low", "低", "低密度", "简单", "简洁"}:
        return "low"
    if text in {"high", "高", "高密度", "复杂", "繁复"}:
        return "high"
    return "medium"


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "1", "yes", "是", "安全"}


def normalize_role(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "背景": "background",
        "主贴纸": "focal_sticker",
        "主体贴图": "focal_sticker",
        "辅助贴纸": "supporting_sticker",
        "胶带": "tape",
        "边框": "frame",
        "装饰": "decoration",
        "无": "none",
    }
    normalized = aliases.get(text, text)
    return normalized if normalized in ROLE_VALUES else "none"


if __name__ == "__main__":
    asyncio.run(main())
