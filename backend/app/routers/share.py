"""Public share links: send a finished clip to anyone, no studio access needed.

A share link is a random slug stored on the project. Everything it exposes is
slug-addressed (video, thumbnail) so the project id never has to leave the studio.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from .. import db
from ..config import PROJECTS_DIR
from ..schemas import ShareRequest

router = APIRouter(prefix="/api", tags=["share"])

QUALITY_ORDER = ("final", "preview")
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}


def _new_slug() -> str:
    # Short, URL-safe, hard to guess (48 bits).
    return secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:9]


def _share_of(project: dict[str, Any]) -> Optional[dict[str, Any]]:
    share = project.get("share")
    return share if isinstance(share, dict) and share.get("slug") else None


def _resolve(project: dict[str, Any], share: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return the render backing a share link, if the file still exists."""
    renders = project.get("renders") or {}
    quality = share.get("quality")
    candidates = [quality] if quality in renders else []
    candidates += [name for name in QUALITY_ORDER if name not in candidates]
    for name in candidates:
        render = renders.get(name) or {}
        file_name = render.get("file")
        if not file_name:
            continue
        path = PROJECTS_DIR / project["id"] / file_name
        if path.is_file():
            return {"quality": name, "render": render, "path": path}
    return None


def _project_by_slug(slug: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for project in db.list_projects():
        share = _share_of(project)
        if share and share["slug"] == slug:
            target = _resolve(project, share)
            if not target:
                raise HTTPException(status_code=410, detail="This clip is no longer available.")
            return project, share, target
    raise HTTPException(status_code=404, detail="Share link not found")


def _file_response(target: dict[str, Any], *, download: bool, title: str) -> FileResponse:
    path: Path = target["path"]
    suffix = path.suffix.lower()
    media_type = "video/mp4" if suffix == ".mp4" else "video/webm" if suffix == ".webm" else "video/quicktime"
    if suffix not in VIDEO_EXTENSIONS:
        media_type = "application/octet-stream"
    disposition = "attachment" if download else "inline"
    safe = "".join(ch for ch in title if ch.isalnum() or ch in "-_ ").strip() or "cliptok"
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=f"{safe}.mp4",
        content_disposition_type=disposition,
        headers={"Cache-Control": "public, max-age=60", "Accept-Ranges": "bytes"},
    )


@router.post("/projects/{project_id}/share", status_code=201)
def create_share(project_id: str, payload: ShareRequest | None = None) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    requested = (payload.quality if payload else None) or "auto"
    renders = project.get("renders") or {}
    if not any(name in renders for name in QUALITY_ORDER):
        raise HTTPException(status_code=400, detail="Render a clip before sharing it.")

    quality = requested
    if quality == "auto" or quality not in renders:
        quality = next((name for name in QUALITY_ORDER if name in renders), "preview")

    existing = _share_of(project)
    if existing and existing.get("quality") == quality:
        return {"share": _decorate(existing)}

    share = {
        "slug": existing["slug"] if existing else _new_slug(),
        "quality": quality,
        "created_at": (existing or {}).get("created_at")
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "refreshed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    updated = db.update_project(project_id, data_patch={"share": share})
    assert updated is not None
    return {"share": _decorate(share)}


@router.delete("/projects/{project_id}/share", status_code=204)
def delete_share(project_id: str) -> JSONResponse:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if _share_of(project):
        db.update_project(project_id, data_patch={"share": None})
    return JSONResponse(status_code=204, content=None)


@router.get("/share/{slug}")
def public_share(slug: str) -> dict:
    project, share, target = _project_by_slug(slug)
    render = target["render"]
    return {
        "slug": slug,
        "title": project["name"],
        "quality": target["quality"],
        "duration": render.get("duration") or project["duration"],
        "width": render.get("width"),
        "height": render.get("height"),
        "preset": render.get("preset"),
        "captions": bool(render.get("captions")),
        "source_kind": project["source_kind"],
        "published_at": share.get("refreshed_at") or share.get("created_at"),
        "video_url": f"/api/share/{slug}/video",
        "thumbnail_url": f"/api/share/{slug}/thumbnail" if render.get("thumbnail") else None,
        "download_url": f"/api/share/{slug}/video?download=1",
    }


@router.get("/share/{slug}/video")
def public_video(slug: str, download: bool = Query(default=False)) -> FileResponse:
    project, _, target = _project_by_slug(slug)
    return _file_response(target, download=download, title=project["name"])


@router.get("/share/{slug}/thumbnail")
def public_thumbnail(slug: str) -> FileResponse:
    project, _, target = _project_by_slug(slug)
    thumb = (target["render"] or {}).get("thumbnail")
    if not thumb:
        raise HTTPException(status_code=404, detail="Not found")
    path = PROJECTS_DIR / project["id"] / thumb
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path=path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=300"})


def _decorate(share: dict[str, Any]) -> dict[str, Any]:
    slug = share["slug"]
    return {
        "slug": slug,
        "quality": share.get("quality"),
        "path": f"/s/{slug}",
        "created_at": share.get("created_at"),
    }
