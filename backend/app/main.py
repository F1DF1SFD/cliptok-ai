"""ClipTok AI API entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import db
from .config import (
    CORS_ORIGINS,
    MAX_CLIP_SECONDS,
    MAX_UPLOAD_BYTES,
    PRESETS,
    WHISPER_MODEL,
)
from .routers import catalog, media, projects, share
from .services import analyze as analyze_service
from .services import transcribe as transcribe_service
from .services.media import ffmpeg_available, ffprobe_available
from .services.overlay import available_fonts
from .services.pipeline import UserError
from .services.twitch import ImportError_, ytdlp_available

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="ClipTok AI",
    version="1.0.0",
    description="Turn Twitch clips into captioned vertical shorts.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges"],
)

app.include_router(projects.router)
app.include_router(media.router)
app.include_router(catalog.router)
app.include_router(share.router)


@app.exception_handler(UserError)
async def user_error_handler(_: Request, exc: UserError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ImportError_)
async def import_error_handler(_: Request, exc: ImportError_) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/api/health")
def health() -> dict:
    capabilities = {
        "ffmpeg": ffmpeg_available(),
        "ffprobe": ffprobe_available(),
        "ytdlp": ytdlp_available(),
        "whisper": transcribe_service.whisper_available(),
        "opencv": analyze_service.opencv_available(),
    }
    return {
        "status": "ok" if capabilities["ffmpeg"] else "degraded",
        "capabilities": capabilities,
        "whisper_model": WHISPER_MODEL,
        "limits": {
            "max_upload_bytes": MAX_UPLOAD_BYTES,
            "max_clip_seconds": MAX_CLIP_SECONDS,
        },
        "presets": list(PRESETS.values()),
        "fonts": available_fonts(),
    }


@app.get("/api/presets")
def presets() -> dict:
    return {"presets": list(PRESETS.values())}


@app.get("/api")
def root() -> dict:
    return {"name": "ClipTok AI API", "docs": "/docs", "health": "/api/health"}
