"""SQLite persistence for projects and background jobs.

The database stores small JSON documents; large binaries live on disk under
``DATA_DIR/projects/<project_id>``.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import DB_PATH, PRESETS
from .schemas import RenderSettings

_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _LOCK, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_url TEXT,
                status TEXT NOT NULL DEFAULT 'ready',
                error TEXT,
                duration REAL NOT NULL DEFAULT 0,
                width INTEGER NOT NULL DEFAULT 0,
                height INTEGER NOT NULL DEFAULT 0,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def default_project_data() -> dict[str, Any]:
    return {
        "files": {},
        "thumbnail": None,
        "transcript": None,
        "analysis": None,
        "music": None,
        "settings": RenderSettings().model_dump(),
        "renders": {},
        "share": None,
    }


def _row_to_project(row: sqlite3.Row) -> dict[str, Any]:
    data = json.loads(row["data"])
    settings = RenderSettings.model_validate(data.get("settings") or {})
    return {
        "id": row["id"],
        "name": row["name"],
        "source_kind": row["source_kind"],
        "source_url": row["source_url"],
        "status": row["status"],
        "error": row["error"],
        "duration": row["duration"],
        "width": row["width"],
        "height": row["height"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "thumbnail": data.get("thumbnail"),
        "files": data.get("files") or {},
        "transcript": data.get("transcript"),
        "analysis": data.get("analysis"),
        "music": data.get("music"),
        "settings": settings.model_dump(),
        "renders": data.get("renders") or {},
        "share": data.get("share"),
    }


def create_project(
    *,
    name: str,
    source_kind: str,
    source_url: Optional[str],
    duration: float,
    width: int,
    height: int,
) -> dict[str, Any]:
    project_id = new_id()
    now = utc_now()
    data = default_project_data()
    with _LOCK, _connect() as conn:
        conn.execute(
            """INSERT INTO projects
               (id, name, source_kind, source_url, status, duration, width, height, data, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'ready', ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                name,
                source_kind,
                source_url,
                duration,
                width,
                height,
                json.dumps(data),
                now,
                now,
            ),
        )
        conn.commit()
    project = get_project(project_id)
    assert project is not None
    return project


def list_projects() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [_row_to_project(row) for row in rows]


def get_project(project_id: str) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _row_to_project(row) if row else None


def update_project(
    project_id: str,
    *,
    name: Optional[str] = None,
    status: Optional[str] = None,
    error: Optional[str] = None,
    settings: Optional[RenderSettings] = None,
    data_patch: Optional[dict[str, Any]] = None,
    duration: Optional[float] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    project = get_project(project_id)
    if not project:
        return None
    data = {
        "files": project["files"],
        "thumbnail": project["thumbnail"],
        "transcript": project["transcript"],
        "analysis": project["analysis"],
        "music": project["music"],
        "settings": project["settings"],
        "renders": project["renders"],
        "share": project.get("share"),
    }
    if data_patch:
        data.update(data_patch)
    if settings is not None:
        data["settings"] = settings.model_dump()
    with _LOCK, _connect() as conn:
        conn.execute(
            """UPDATE projects SET name = ?, status = ?, error = ?, data = ?,
               duration = ?, width = ?, height = ?, updated_at = ?
               WHERE id = ?""",
            (
                name if name is not None else project["name"],
                status if status is not None else project["status"],
                error,
                json.dumps(data),
                duration if duration is not None else project["duration"],
                width if width is not None else project["width"],
                height if height is not None else project["height"],
                utc_now(),
                project_id,
            ),
        )
        conn.commit()
    return get_project(project_id)


def delete_project(project_id: str) -> bool:
    with _LOCK, _connect() as conn:
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.execute("DELETE FROM jobs WHERE project_id = ?", (project_id,))
        conn.commit()
    return cur.rowcount > 0


def project_dir(project_id: str) -> Path:
    from .config import PROJECTS_DIR

    path = PROJECTS_DIR / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_job(project_id: str, kind: str) -> dict[str, Any]:
    job_id = new_id()
    now = utc_now()
    with _LOCK, _connect() as conn:
        conn.execute(
            """INSERT INTO jobs (id, project_id, kind, status, progress, message, created_at, updated_at)
               VALUES (?, ?, ?, 'queued', 0, ?, ?, ?)""",
            (job_id, project_id, kind, "Queued", now, now),
        )
        conn.commit()
    job = get_job(job_id)
    assert job is not None
    return job


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "kind": row["kind"],
        "status": row["status"],
        "progress": row["progress"],
        "message": row["message"],
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def update_job(
    job_id: str,
    *,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    job = get_job(job_id)
    if not job:
        return
    with _LOCK, _connect() as conn:
        conn.execute(
            """UPDATE jobs SET status = ?, progress = ?, message = ?, error = ?, updated_at = ?
               WHERE id = ?""",
            (
                status if status is not None else job["status"],
                progress if progress is not None else job["progress"],
                message if message is not None else job["message"],
                error if error is not None else job["error"],
                utc_now(),
                job_id,
            ),
        )
        conn.commit()


def active_job(project_id: str) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM jobs WHERE project_id = ? AND status IN ('queued','running') "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (project_id,),
        ).fetchone()
    return get_job(row["id"]) if row else None


def preset_for(settings: RenderSettings) -> dict[str, Any]:
    return PRESETS[settings.preset]
