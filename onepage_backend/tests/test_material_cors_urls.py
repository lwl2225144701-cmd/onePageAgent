from datetime import datetime, timezone
from uuid import uuid4

from fastapi.responses import Response
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.v1 import materials as materials_api
from app.main import app
from app.services.material_urls import build_material_proxy_url, build_material_proxy_urls


async def _dummy_db():
    yield None


def _client(monkeypatch):
    async def fake_serve_material_binary(*, material_id: str, variant: str, user_id: str | None, db):
        media_type = "image/svg+xml" if variant == "preview" else "image/png"
        content = b"<svg></svg>" if variant == "preview" else b"\x89PNG\r\n\x1a\n"
        return Response(content=content, media_type=media_type)

    monkeypatch.setattr(materials_api, "_serve_material_binary", fake_serve_material_binary)
    app.dependency_overrides[get_db] = _dummy_db
    return TestClient(app)


def test_material_asset_cors_allows_localhost_origin(monkeypatch):
    client = _client(monkeypatch)
    try:
        response = client.get(
            f"/api/materials/{uuid4()}/asset?anonymous_user_id=user-a&v=123",
            headers={"Origin": "http://localhost:3000"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["content-type"] == "image/png"


def test_material_preview_cors_allows_127_origin(monkeypatch):
    client = _client(monkeypatch)
    try:
        response = client.get(
            f"/api/materials/{uuid4()}/preview?anonymous_user_id=user-a&v=123",
            headers={"Origin": "http://127.0.0.1:3000"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert response.headers["content-type"] == "image/svg+xml"


def test_material_cors_rejects_unknown_origin(monkeypatch):
    client = _client(monkeypatch)
    try:
        response = client.get(
            f"/api/materials/{uuid4()}/asset",
            headers={"Origin": "http://malicious.example"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_material_cors_preflight_exposes_expected_methods():
    client = TestClient(app)
    response = client.options(
        f"/api/materials/{uuid4()}/asset",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_material_proxy_url_defaults_to_relative_api_and_keeps_query_params():
    material_id = uuid4()

    class MaterialStub:
        id = material_id
        created_at = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        updated_at = None

    preview_url, file_url = build_material_proxy_urls(MaterialStub(), "user-a")

    assert preview_url.startswith(f"/api/materials/{material_id}/preview?")
    assert file_url.startswith(f"/api/materials/{material_id}/asset?")
    assert "anonymous_user_id=user-a" in file_url
    assert "v=" in file_url
    assert "127.0.0.1:8000" not in file_url


def test_material_proxy_url_handles_anonymous_user_encoding():
    material_id = uuid4()

    class MaterialStub:
        id = material_id
        created_at = None
        updated_at = None

    url = build_material_proxy_url(MaterialStub(), "asset", "user with space")

    assert url == f"/api/materials/{material_id}/asset?anonymous_user_id=user+with+space"
