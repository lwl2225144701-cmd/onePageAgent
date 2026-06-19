from __future__ import annotations

from urllib.parse import urlencode

from app.config import settings


def build_material_proxy_url(material, variant: str, user_id: str | None = None) -> str:
    base = _public_api_base_url()
    url = f"{base}/materials/{material.id}/{variant}"
    params: dict[str, str | int] = {}
    if user_id:
        params["anonymous_user_id"] = user_id
    version_source = getattr(material, "updated_at", None) or getattr(material, "created_at", None)
    if version_source is not None:
        params["v"] = int(version_source.timestamp())
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


def build_material_proxy_urls(material, user_id: str | None = None) -> tuple[str, str]:
    preview_url = build_material_proxy_url(material, "preview", user_id)
    file_url = build_material_proxy_url(material, "asset", user_id)
    print(
        "MATERIAL_URL_BUILT "
        f"material_id={material.id} "
        f"preview_url={preview_url} "
        f"file_url={file_url}",
        flush=True,
    )
    return preview_url, file_url


def _public_api_base_url() -> str:
    base = str(settings.PUBLIC_API_BASE_URL or "").strip().rstrip("/")
    if not base:
        base = settings.API_V1_PREFIX
    if base.startswith(("http://", "https://", "/")):
        return base
    return f"/{base}"
