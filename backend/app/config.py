"""Runtime configuration for the ClipTok AI backend."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("CLIPTOK_DATA_DIR", BASE_DIR / "data")).resolve()
PROJECTS_DIR = DATA_DIR / "projects"
DB_PATH = DATA_DIR / "cliptok.db"
SFX_DIR = DATA_DIR / "sfx"

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
SFX_DIR.mkdir(parents=True, exist_ok=True)

# FFmpeg / yt-dlp binaries (override with env vars if they live elsewhere).
FFMPEG = os.getenv("CLIPTOK_FFMPEG", shutil.which("ffmpeg") or "ffmpeg")
FFPROBE = os.getenv("CLIPTOK_FFPROBE", shutil.which("ffprobe") or "ffprobe")
YTDLP = os.getenv("CLIPTOK_YTDLP", shutil.which("yt-dlp") or "yt-dlp")

# Whisper
WHISPER_MODEL = os.getenv("CLIPTOK_WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("CLIPTOK_WHISPER_DEVICE", "auto")
WHISPER_COMPUTE = os.getenv("CLIPTOK_WHISPER_COMPUTE", "int8")

# CORS origins for the Next.js frontend.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CLIPTOK_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

MAX_UPLOAD_BYTES = int(os.getenv("CLIPTOK_MAX_UPLOAD_MB", "512")) * 1024 * 1024
MAX_CLIP_SECONDS = float(os.getenv("CLIPTOK_MAX_CLIP_SECONDS", "600"))

# Export presets - all short-form vertical formats.
PRESETS: dict[str, dict] = {
    "tiktok": {
        "id": "tiktok",
        "label": "TikTok",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "video_bitrate": "8M",
        "description": "1080x1920 - 8 Mbps, safe zones clear of the TikTok UI",
    },
    "shorts": {
        "id": "shorts",
        "label": "YouTube Shorts",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "video_bitrate": "10M",
        "description": "1080x1920 - 10 Mbps, higher bitrate for YouTube",
    },
    "reels": {
        "id": "reels",
        "label": "Instagram Reels",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "video_bitrate": "8M",
        "description": "1080x1920 - 8 Mbps, H.264 + AAC for Reels uploads",
    },
}

PREVIEW_SCALE = 0.5  # preview renders at half resolution
