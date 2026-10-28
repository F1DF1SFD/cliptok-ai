"""Tiny in-process job runner.

Long tasks (transcription, analysis, rendering) are executed in a thread pool
so the API stays responsive. Progress is persisted in SQLite and polled by the
UI through ``GET /api/jobs/{id}``.
"""

from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from . import db

log = logging.getLogger("cliptok.jobs")

POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cliptok-job")


class JobReporter:
    """Callable passed to workers to publish progress."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id

    def __call__(self, progress: float, message: str) -> None:
        db.update_job(
            self.job_id,
            status="running",
            progress=max(0.0, min(1.0, progress)),
            message=message,
        )


def submit(project_id: str, kind: str, func: Callable[[JobReporter], None]) -> dict:
    job = db.create_job(project_id, kind)

    def _run() -> None:
        reporter = JobReporter(job["id"])
        db.update_job(job["id"], status="running", progress=0.01, message="Starting")
        try:
            func(reporter)
        except Exception as exc:  # pragma: no cover - defensive
            log.error("job %s (%s) failed: %s", job["id"], kind, exc)
            log.debug("%s", traceback.format_exc())
            db.update_job(
                job["id"],
                status="failed",
                error=str(exc) or exc.__class__.__name__,
                message="Failed",
            )
            return
        db.update_job(job["id"], status="succeeded", progress=1.0, message="Done")

    POOL.submit(_run)
    return job
