from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "onepage_backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")
except Exception:
    pass

from app.ai.gateway.dashscope_vision_client import DashScopeVisionReviewClient, validate_data_url_size  # noqa: E402
from app.ai.pipeline.step4_material_review import _build_contact_sheet, _parse_json_content, _vision_prompt  # noqa: E402
from app.config import settings  # noqa: E402


def _find_images(limit: int) -> list[Path]:
    roots = [
        ROOT / "素材2.0",
        ROOT / "onepage_backend" / "tests" / "fixtures",
    ]
    images: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} and path.is_file():
                images.append(path)
                if len(images) >= limit:
                    return images
    return images


async def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test DashScope qwen3-omni-flash material review with a local contact sheet.")
    parser.add_argument("images", nargs="*", help="2-4 local material image paths")
    parser.add_argument("--limit", type=int, default=4)
    args = parser.parse_args()

    if not os.getenv("DASHSCOPE_API_KEY") and not settings.DASHSCOPE_API_KEY:
        print(json.dumps({"ok": False, "error": "missing_DASHSCOPE_API_KEY"}, ensure_ascii=False))
        return 2

    image_paths = [Path(item).expanduser().resolve() for item in args.images]
    image_paths = [path for path in image_paths if path.exists() and path.is_file()]
    if not image_paths:
        image_paths = _find_images(max(2, min(4, args.limit)))
    image_paths = image_paths[: max(2, min(4, args.limit))]
    if not image_paths:
        print(json.dumps({"ok": False, "error": "no_local_images_found"}, ensure_ascii=False))
        return 2

    items = [
        {
            "material_id": f"local-{index}",
            "name": path.stem,
            "type": "sticker",
            "category": "本地素材",
            "_source": {"origin_path": str(path)},
        }
        for index, path in enumerate(image_paths, start=1)
    ]
    contact_sheet = _build_contact_sheet(items)
    if not contact_sheet:
        print(json.dumps({"ok": False, "error": "contact_sheet_build_failed"}, ensure_ascii=False))
        return 2

    data_url, sheet_items = contact_sheet
    data_url_bytes = validate_data_url_size(data_url)
    prompt = _vision_prompt(
        user_text="今天吃了一家很好吃的饺子店，给它点赞。",
        semantic={
            "scene": "daily_life",
            "sub_scene": "food_review",
            "intent": "food_record",
            "positive_tags": ["food", "daily", "warm", "happy", "review"],
            "avoid_tags": ["party", "family", "ballet", "dance", "wedding", "romance", "bouquet"],
        },
        items=sheet_items,
    )

    client = DashScopeVisionReviewClient()
    started = time.perf_counter()
    try:
        response = await client.review_contact_sheet(
            prompt=prompt,
            contact_sheet_data_url=data_url,
            task_id="dashscope-smoke",
        )
    finally:
        await client.close()

    parsed = _parse_json_content(response.get("content"))
    print(
        json.dumps(
            {
                "ok": bool(parsed),
                "model": settings.VISION_REVIEW_MODEL,
                "image_count": len(sheet_items),
                "data_url_bytes": data_url_bytes,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "usage": response.get("usage", {}),
                "review": parsed,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
