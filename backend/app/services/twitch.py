"""Downloading Twitch clips / VOD highlights with yt-dlp.

We intentionally rely on yt-dlp rather than the Twitch Helix API: it works for
clip URLs without an app client id, resolves clip slugs to the underlying MP4
and also handles VOD links with timestamps.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ..config import YTDLP

TWITCH_HOSTS = {"twitch.tv", "www.twitch.tv", "m.twitch.tv", "clips.twitch.tv", "go.twitch.tv"}
ALLOWED_SCHEMES = {"http", "https"}


class ImportError_(RuntimeError):
    """User-facing import failure."""


@dataclass
class ImportedClip:
    path: Path
    title: str
    duration: float
    source_url: str
    creator: str = ""
    thumbnail_url: str = ""
    width: int = 0
    height: int = 0


def ytdlp_available() -> bool:
    try:
        subprocess.run([YTDLP, "--version"], capture_output=True, timeout=15, check=True)
        return True
    except Exception:
        return False


def validate_twitch_url(url: str) -> str:
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ImportError_("Only http(s) links are supported.")
    host = (parsed.hostname or "").lower()
    if host not in TWITCH_HOSTS:
        raise ImportError_(
            "That link isn't a Twitch clip. Paste a clips.twitch.tv or twitch.tv/<channel>/clip/<slug> URL."
        )
    return url



def _metadata(url: str) -> dict:
    try:
        proc = subprocess.run(
            [YTDLP, "-J", "--no-warnings", "--no-playlist", url],
            capture_output=True,
            timeout=180,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ImportError_(
            "yt-dlp is not installed. Install it with `brew install yt-dlp` and restart the API."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ImportError_("Twitch took too long to respond. Try again in a moment.") from exc
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-4:]
        raise ImportError_("Could not read that clip. " + " ".join(tail))
    try:
        return json.loads(proc.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise ImportError_("Twitch returned an unexpected response.") from exc


def fetch_clip(url: str, dest_dir: Path, *, max_duration: float = 600) -> ImportedClip:
    """Download a Twitch clip into ``dest_dir`` as ``source.mp4``."""
    url = validate_twitch_url(url)
    info = _metadata(url)
    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        if not entries:
            raise ImportError_("No downloadable clip found at that URL.")
        info = entries[0]

    duration = float(info.get("duration") or 0)
    if duration and duration > max_duration:
        raise ImportError_(
            f"That source is {duration / 60:.0f} minutes long. Clip it on Twitch first "
            f"(limit {max_duration / 60:.0f} minutes)."
        )

    dest_dir.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(dest_dir / "source.%(ext)s")
    proc = subprocess.run(
        [
            YTDLP,
            "--no-warnings",
            "--no-playlist",
            "-f",
            "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b[height<=1080]/b",
            "--merge-output-format",
            "mp4",
            "--recode-video",
            "mp4",
            "-o",
            out_tmpl,
            "--print",
            "after_move:filepath",
            url,
        ],
        capture_output=True,
        timeout=900,
        check=False,
    )
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-6:]
        raise ImportError_("Download failed. " + " ".join(tail))

    candidates = sorted(dest_dir.glob("source.*"))
    video = next((p for p in candidates if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}), None)
    if not video:
        raise ImportError_("Download finished but no video file was produced.")
    if video.suffix.lower() != ".mp4":
        mp4 = dest_dir / "source.mp4"
        from .media import run, FFMPEG  # local import to avoid a cycle

        run([FFMPEG, "-hide_banner", "-y", "-i", str(video), "-c", "copy", str(mp4)], timeout=600)
        video.unlink(missing_ok=True)
        video = mp4

    return ImportedClip(
        path=video,
        title=str(info.get("title") or "Twitch clip").strip(),
        duration=duration,
        source_url=url,
        creator=str(info.get("uploader") or info.get("channel") or "").strip(),
        thumbnail_url=str(info.get("thumbnail") or ""),
        width=int(info.get("width") or 0),
        height=int(info.get("height") or 0),
    )
