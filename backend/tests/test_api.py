from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_capabilities():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        payload = response.json()
        assert "capabilities" in payload
        assert payload["limits"]["max_clip_seconds"] > 0
        assert any(preset["id"] == "tiktok" for preset in payload["presets"])


def test_project_list_is_empty_for_fresh_install():
    with TestClient(app) as client:
        response = client.get("/api/projects")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_twitch_import_rejects_non_twitch_hosts():
    with TestClient(app) as client:
        response = client.post(
            "/api/projects/import", json={"url": "https://example.com/not-a-clip"}
        )
        assert response.status_code == 400
        assert "Twitch" in response.json()["detail"]


def test_upload_rejects_unsupported_file_types():
    with TestClient(app) as client:
        response = client.post(
            "/api/projects/upload",
            files={"file": ("notes.txt", b"not a video", "text/plain")},
        )
        assert response.status_code == 400
        assert "Unsupported" in response.json()["detail"]


def test_catalog_endpoints_return_fonts_and_stickers():
    with TestClient(app) as client:
        fonts = client.get("/api/fonts").json()["fonts"]
        stickers = client.get("/api/stickers").json()["stickers"]
        assert "Arial Black" in fonts
        assert any(sticker["id"] == "fire" for sticker in stickers)
        response = client.get("/api/stickers/fire.png")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
