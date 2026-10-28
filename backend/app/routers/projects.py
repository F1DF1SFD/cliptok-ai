"""HTTP API for projects, jobs and rendering."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .. import db, jobs
from ..config import MAX_UPLOAD_BYTES
from ..schemas import (
    ImportRequest,
    ProjectSettingsUpdate,
    RenderRequest,
    RenderSettings,
    Transcript,
)
from ..services import pipeline
from ..services.analyze import overview
from ..services.captions import caption_events
from ..services.media import MediaError
from ..services.pipeline import UserError, settings_hash
from ..services.twitch import ImportError_

router = APIRouter(prefix="/api", tags=["projects"])

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


def _url(project_id: str, name: Optional[str], stamp: str) -> Optional[str]:
    if not name:
        return None
    return f"/api/media/{project_id}/{name}?v={quote(stamp)}"


def serialize(project: dict, *, full: bool = True) -> dict:
    project_id = project["id"]
    stamp = str(project.get("updated_at") or "")
    renders = project.get("renders") or {}
    current_hash = settings_hash(RenderSettings.model_validate(project["settings"]))
    urls = {
        "source": _url(project_id, (project.get("files") or {}).get("source"), stamp),
        "thumbnail": _url(project_id, project.get("thumbnail"), stamp),
        "preview": _url(project_id, (renders.get("preview") or {}).get("file"), stamp),
        "preview_thumbnail": _url(project_id, (renders.get("preview") or {}).get("thumbnail"), stamp),
        "final": _url(project_id, (renders.get("final") or {}).get("file"), stamp),
        "final_thumbnail": _url(project_id, (renders.get("final") or {}).get("thumbnail"), stamp),
        "music": _url(project_id, project.get("music"), stamp),
    }
    payload = {
        "id": project_id,
        "name": project["name"],
        "source_kind": project["source_kind"],
        "source_url": project.get("source_url"),
        "status": project["status"],
        "error": project.get("error"),
        "duration": project["duration"],
        "width": project["width"],
        "height": project["height"],
        "created_at": project["created_at"],
        "updated_at": project["updated_at"],
        "settings": project["settings"],
        "renders": renders,
        "has_transcript": bool(project.get("transcript")),
        "has_music": bool(project.get("music")),
        "analysis_summary": overview(project["analysis"]) if project.get("analysis") else None,
        "active_job": db.active_job(project_id),
        "urls": urls,
        "share": project.get("share") or None,
        "stale": {
            "preview": bool(renders.get("preview"))
            and renders["preview"].get("settings_hash") != current_hash,
            "final": bool(renders.get("final"))
            and renders["final"].get("settings_hash") != current_hash,
        },
    }
    if full:
        transcript = project.get("transcript")
        payload["caption_lines"] = (
            caption_events(
                Transcript.model_validate(transcript),
                RenderSettings.model_validate(project["settings"]).captions,
            )
            if transcript
            else []
        )
        payload["transcript"] = None
        if transcript:
            words = transcript.get("words") or []
            segments = transcript.get("segments") or []
            payload["transcript"] = {
                "language": transcript.get("language"),
                "language_probability": transcript.get("language_probability"),
                "text": transcript.get("text"),
                "word_count": len(words),
                "segment_count": len(segments),
                "preview_words": [
                    {"word": w["word"], "start": w["start"], "end": w["end"]} for w in words[:60]
                ],
            }
    return payload


@router.get("/projects")
def list_projects() -> list[dict]:
    return [serialize(project, full=False) for project in db.list_projects()]


@router.post("/projects/import", status_code=201)
def import_twitch(payload: ImportRequest) -> dict:
    try:
        project = pipeline.import_twitch(payload.url)
    except ImportError_ as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (MediaError, UserError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize(project)


@router.post("/projects/upload", status_code=201)
async def upload_project(file: UploadFile = File(...)) -> dict:
    filename = file.filename or "upload.mp4"
    suffix = Path(filename).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix or 'unknown'}'. Upload MP4, MOV, WebM or MKV.",
        )

    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="cliptok-upload-")
    tmp_path = Path(handle.name)
    size = 0
    try:
        with handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                    )
                handle.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        project = pipeline.create_from_upload(filename, tmp_path)
        return serialize(project)
    except (MediaError, UserError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()
        tmp_path.unlink(missing_ok=True)


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return serialize(project)


@router.patch("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectSettingsUpdate) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    new_name: Optional[str] = None
    if payload.name is not None:
        new_name = (payload.name or "").strip()[:120] or "Untitled clip"
    updated = db.update_project(project_id, name=new_name, settings=payload.settings)
    assert updated is not None
    return serialize(updated)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str) -> JSONResponse:
    if not db.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    pipeline.delete(project_id)
    return JSONResponse(status_code=204, content=None)


@router.post("/projects/{project_id}/transcribe", status_code=202)
def transcribe_project(project_id: str) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if db.active_job(project_id):
        raise HTTPException(status_code=409, detail="Another job is already running for this project")
    job = jobs.submit(
        project_id,
        "transcribe",
        lambda report: pipeline.transcribe_project(project_id, report),
    )
    return job


@router.post("/projects/{project_id}/analyze", status_code=202)
def analyze_project(project_id: str) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if db.active_job(project_id):
        raise HTTPException(status_code=409, detail="Another job is already running for this project")
    job = jobs.submit(
        project_id,
        "analyze",
        lambda report: pipeline.analyze_project(project_id, report),
    )
    return job


@router.post("/projects/{project_id}/render", status_code=202)
def render_project(project_id: str, payload: RenderRequest) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if db.active_job(project_id):
        raise HTTPException(status_code=409, detail="Another job is already running for this project")
    quality = payload.quality
    job = jobs.submit(
        project_id,
        f"render:{quality}",
        lambda report: pipeline.render(project_id, quality, report),
    )
    return job


@router.post("/projects/{project_id}/music", status_code=201)
async def upload_music(project_id: str, file: UploadFile = File(...)) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "music.mp3").suffix)
    tmp_path = Path(handle.name)
    try:
        total = 0
        with handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 30 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Music files are limited to 30 MB.")
                handle.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        updated = pipeline.set_music(project_id, file.filename or "music.mp3", tmp_path)
        return serialize(updated)
    except UserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()
        tmp_path.unlink(missing_ok=True)


@router.delete("/projects/{project_id}/music")
def delete_music(project_id: str) -> dict:
    if not db.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return serialize(pipeline.remove_music(project_id))


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
