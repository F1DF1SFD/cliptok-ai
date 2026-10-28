"""Project orchestration: import, transcribe, analyse and render."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from .. import db
from ..config import MAX_CLIP_SECONDS, PROJECTS_DIR
from ..schemas import RenderSettings, Transcript
from . import analyze as analyze_mod
from .media import MediaError, extract_audio, make_thumbnail, probe
from .render import render_project
from .transcribe import transcribe
from .twitch import fetch_clip

ProgressFn = Callable[[float, str], None]


class UserError(RuntimeError):
    """An error safe to show directly in the UI."""


def source_file(project: dict) -> Path:
    return db.project_dir(project["id"]) / "source.mp4"


def settings_hash(settings: RenderSettings) -> str:
    payload = json.dumps(settings.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _finalize(project_id: str, video: Path, *, name: str, source_kind: str, source_url: Optional[str]) -> dict:
    info = probe(video)
    if info.duration <= 0.5:
        raise UserError("That video is too short to process.")
    if info.duration > MAX_CLIP_SECONDS:
        raise UserError(
            f"Clips are limited to {MAX_CLIP_SECONDS / 60:.0f} minutes. Trim it first."
        )

    target = db.project_dir(project_id) / "source.mp4"
    if video.resolve() != target.resolve():
        shutil.move(str(video), target)
    thumb = db.project_dir(project_id) / "thumbnail.jpg"
    try:
        make_thumbnail(target, thumb, min(1.0, info.duration / 2))
    except MediaError:
        thumb = None
    project = db.update_project(
        project_id,
        name=name[:120] or "Untitled clip",
        duration=info.duration,
        width=info.width,
        height=info.height,
        status="ready",
        data_patch={
            "files": {"source": "source.mp4"},
            "thumbnail": "thumbnail.jpg" if thumb and thumb.exists() else None,
            "renders": {},
        },
    )
    assert project is not None
    return project


def import_twitch(url: str) -> dict:
    """Download a Twitch clip and register it as a project."""
    project = db.create_project(
        name="Importing clip...",
        source_kind="twitch",
        source_url=url,
        duration=0,
        width=0,
        height=0,
    )
    project_id = project["id"]
    try:
        clip = fetch_clip(url, db.project_dir(project_id), max_duration=MAX_CLIP_SECONDS)
        return _finalize(
            project_id, clip.path, name=clip.title or "Twitch clip", source_kind="twitch", source_url=url
        )
    except Exception:
        shutil.rmtree(PROJECTS_DIR / project_id, ignore_errors=True)
        db.delete_project(project_id)
        raise
    finally:
        pass


def create_from_upload(filename: str, tmp_path: Path) -> dict:
    """Register an already-saved upload as a project."""
    project = db.create_project(
        name=Path(filename).stem.replace("_", " ").strip()[:120] or "Uploaded clip",
        source_kind="upload",
        source_url=None,
        duration=0,
        width=0,
        height=0,
    )
    try:
        return _finalize(
            project["id"], tmp_path, name=Path(filename).stem.replace("_", " ").strip() or "Uploaded clip",
            source_kind="upload", source_url=None,
        )
    except Exception:
        shutil.rmtree(PROJECTS_DIR / project["id"], ignore_errors=True)
        db.delete_project(project["id"])
        raise


def transcribe_project(project_id: str, report: ProgressFn) -> None:
    project = db.get_project(project_id)
    if not project:
        raise UserError("Project not found")
    video = source_file(project)
    if not video.exists():
        raise UserError("Source video is missing")

    audio = video.parent / "audio.wav"
    report(0.02, "Extracting audio")
    if not audio.exists():
        extract_audio(video, audio)

    transcript = transcribe(audio, progress=lambda value, message: report(0.05 + value * 0.9, message))
    db.update_project(
        project_id,
        data_patch={"transcript": transcript.model_dump()},
        status="ready",
        error=None,
    )


def analyze_project(project_id: str, report: ProgressFn, *, settings: Optional[RenderSettings] = None) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise UserError("Project not found")
    settings = settings or RenderSettings.model_validate(project["settings"])
    result = analyze_mod.analyze_video(
        source_file(project),
        progress=report,
        focus=settings.reframe.focus,
        smoothing=settings.reframe.smoothing,
    )
    db.update_project(project_id, data_patch={"analysis": result}, status="ready", error=None)
    return result


def render(
    project_id: str,
    quality: str,
    report: ProgressFn,
) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise UserError("Project not found")
    source = source_file(project)
    if not source.exists():
        raise UserError("Source video is missing")

    settings = RenderSettings.model_validate(project["settings"])
    report(0.02, "Preparing project")

    analysis = project.get("analysis")
    if not analysis or analysis.get("focus") != settings.reframe.focus or not analysis.get("trajectory"):
        analysis = analyze_project(
            project_id,
            lambda value, message: report(0.02 + value * 0.18, message),
            settings=settings,
        )

    transcript = None
    if project.get("transcript") and settings.captions.enabled:
        transcript = Transcript.model_validate(project["transcript"])

    music = None
    if project.get("music"):
        candidate = db.project_dir(project_id) / project["music"]
        if candidate.exists():
            music = candidate

    out_path = db.project_dir(project_id) / "renders" / f"{quality}.mp4"
    result = render_project(
        project=project,
        source=source,
        quality=quality,
        out_path=out_path,
        work_dir=db.project_dir(project_id) / "work" / quality,
        analysis=analysis,
        transcript=transcript,
        music=music,
        progress=lambda value, message: report(0.2 + value * 0.75, message),
    )

    thumb_name = f"renders/{quality}.jpg"
    try:
        make_thumbnail(out_path, db.project_dir(project_id) / thumb_name, min(1.0, result["duration"] / 2))
    except Exception:
        thumb_name = None

    renders = dict(project.get("renders") or {})
    renders[quality] = {
        "file": f"renders/{quality}.mp4",
        "thumbnail": thumb_name,
        "width": result["width"],
        "height": result["height"],
        "duration": result["duration"],
        "size_bytes": result["size_bytes"],
        "preset": result["preset"],
        "punch_ins": result["punch_ins"],
        "facecam_split": result["facecam_split"],
        "captions": result["captions"],
        "settings_hash": settings_hash(settings),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    db.update_project(project_id, data_patch={"renders": renders}, status="ready", error=None)
    return result


def set_music(project_id: str, filename: str, tmp_path: Path) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise UserError("Project not found")
    suffix = Path(filename).suffix.lower() or ".mp3"
    if suffix not in {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}:
        raise UserError("Upload an MP3, M4A, WAV, AAC, OGG or FLAC file.")
    target = db.project_dir(project_id) / f"music{suffix}"
    for stale in db.project_dir(project_id).glob("music.*"):
        stale.unlink(missing_ok=True)
    shutil.move(str(tmp_path), target)
    db.update_project(project_id, data_patch={"music": target.name})
    return db.get_project(project_id) or project


def remove_music(project_id: str) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise UserError("Project not found")
    for stale in db.project_dir(project_id).glob("music.*"):
        stale.unlink(missing_ok=True)
    db.update_project(project_id, data_patch={"music": None})
    return db.get_project(project_id) or project


def delete(project_id: str) -> None:
    db.delete_project(project_id)
    shutil.rmtree(PROJECTS_DIR / project_id, ignore_errors=True)

