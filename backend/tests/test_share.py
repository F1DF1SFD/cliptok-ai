"""Public share links: creation, lookup and revocation."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.main import app


def _project_with_render(name: str = "clutch play") -> dict:
    project = db.create_project(
        name=name, source_kind="upload", source_url=None, duration=12.0, width=1080, height=1920
    )
    renders_dir = db.project_dir(project["id"]) / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)
    video = renders_dir / "final.mp4"
    video.write_bytes(b"\x00" * 1024)
    thumb = renders_dir / "final.jpg"
    thumb.write_bytes(b"\xff\xd8\xff")
    db.update_project(
        project["id"],
        data_patch={
            "renders": {
                "final": {
                    "file": "renders/final.mp4",
                    "thumbnail": "renders/final.jpg",
                    "width": 1080,
                    "height": 1920,
                    "duration": 12.0,
                    "size_bytes": 1024,
                    "preset": "tiktok",
                    "captions": True,
                }
            }
        },
    )
    updated = db.get_project(project["id"])
    assert updated is not None
    return updated


def test_share_requires_a_rendered_clip():
    project = db.create_project(
        name="no render yet", source_kind="upload", source_url=None, duration=5, width=1280, height=720
    )
    with TestClient(app) as client:
        response = client.post(f"/api/projects/{project['id']}/share", json={"quality": "auto"})
    assert response.status_code == 400
    assert "Render" in response.json()["detail"]


def test_share_lifecycle():
    project = _project_with_render()

    with TestClient(app) as client:
        created = client.post(f"/api/projects/{project['id']}/share", json={"quality": "auto"})
        assert created.status_code in (200, 201)
        share = created.json()["share"]
        assert share["quality"] == "final"
        assert share["path"] == f"/s/{share['slug']}"

        # The slug is exposed on the project so the editor can show the link.
        detail = client.get(f"/api/projects/{project['id']}").json()
        assert detail["share"]["slug"] == share["slug"]

        public = client.get(f"/api/share/{share['slug']}")
        assert public.status_code == 200
        info = public.json()
        assert info["title"] == project["name"]
        assert info["video_url"] == f"/api/share/{share['slug']}/video"
        assert info["width"] == 1080

        video = client.get(info["video_url"])
        assert video.status_code == 200
        assert video.headers["content-type"] == "video/mp4"
        assert video.headers["content-disposition"].startswith("inline")

        download = client.get(f"{info['video_url']}?download=1")
        assert download.headers["content-disposition"].startswith("attachment")

        assert client.get("/api/share/doesnotexist").status_code == 404

        # Creating again is idempotent, it keeps the same slug.
        again = client.post(f"/api/projects/{project['id']}/share", json={"quality": "auto"})
        assert again.json()["share"]["slug"] == share["slug"]

        assert client.delete(f"/api/projects/{project['id']}/share").status_code == 204
        assert client.get(f"/api/share/{share['slug']}").status_code == 404
        assert client.get(f"/api/projects/{project['id']}").json()["share"] is None


def test_share_survives_a_missing_file_with_410(tmp_path: Path):
    project = _project_with_render(name="vanishing clip")
    with TestClient(app) as client:
        slug = client.post(f"/api/projects/{project['id']}/share").json()["share"]["slug"]
        (db.project_dir(project["id"]) / "renders" / "final.mp4").unlink()
        (db.project_dir(project["id"]) / "renders" / "final.jpg").unlink()
        response = client.get(f"/api/share/{slug}")
    assert response.status_code == 410
