"""Serving project media with range support (needed for <video> seeking)."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import PROJECTS_DIR

router = APIRouter(prefix="/api/media", tags=["media"])

EXTRA_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ass": "text/plain; charset=utf-8",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


@router.get("/{project_id}/{file_path:path}")
def get_media(project_id: str, file_path: str) -> FileResponse:
    root = (PROJECTS_DIR / project_id).resolve()
    target = (root / file_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    suffix = target.suffix.lower()
    media_type = EXTRA_TYPES.get(suffix) or mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    return FileResponse(
        path=target,
        media_type=media_type,
        headers={"Cache-Control": "no-store", "Accept-Ranges": "bytes"},
    )
