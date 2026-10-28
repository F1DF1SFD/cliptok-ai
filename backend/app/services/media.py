"""FFmpeg / ffprobe helpers used across the pipeline."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..config import FFMPEG, FFPROBE


class MediaError(RuntimeError):
    """Raised when ffmpeg or ffprobe fails."""


@dataclass
class MediaInfo:
    width: int
    height: int
    duration: float
    fps: float
    has_audio: bool
    video_codec: str = ""
    audio_codec: str = ""


def ffmpeg_available() -> bool:
    try:
        run([FFMPEG, "-version"], timeout=10)
        return True
    except Exception:
        return False


def ffprobe_available() -> bool:
    try:
        run([FFPROBE, "-version"], timeout=10)
        return True
    except Exception:
        return False


def run(cmd: Sequence[str], *, timeout: float = 900) -> subprocess.CompletedProcess:
    """Run a subprocess, raising MediaError with a useful tail on failure."""
    try:
        proc = subprocess.run(
            list(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MediaError(f"Command not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"Command timed out after {timeout:.0f}s: {cmd[0]}") from exc
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-12:]
        raise MediaError("\n".join(tail) or f"{cmd[0]} exited with code {proc.returncode}")
    return proc


def probe(path: Path) -> MediaInfo:
    proc = run(
        [
            FFPROBE,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        timeout=120,
    )
    payload = json.loads(proc.stdout.decode("utf-8", "replace") or "{}")
    streams = payload.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video:
        raise MediaError("No video stream found in the file")

    duration = float(payload.get("format", {}).get("duration") or video.get("duration") or 0)
    fps = 30.0
    rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "30/1"
    try:
        num, _, den = str(rate).partition("/")
        fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    except (TypeError, ValueError, ZeroDivisionError):
        fps = 30.0
    return MediaInfo(
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        duration=round(duration, 3),
        fps=round(fps or 30.0, 3),
        has_audio=audio is not None,
        video_codec=str(video.get("codec_name") or ""),
        audio_codec=str(audio.get("codec_name") or "") if audio else "",
    )


def make_thumbnail(video: Path, out: Path, at: float, width: int = 960) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{max(at, 0):.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-2",
            "-q:v",
            "3",
            str(out),
        ],
        timeout=120,
    )


def extract_audio(video: Path, out: Path, sample_rate: int = 16000) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(out),
        ],
        timeout=600,
    )
    return out


def decode_audio_mono(video: Path, sample_rate: int = 8000) -> bytes:
    """Decode the audio track to raw signed 16-bit mono PCM."""
    proc = run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-f",
            "s16le",
            "-",
        ],
        timeout=600,
    )
    return proc.stdout

