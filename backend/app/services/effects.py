"""Sound effects and punch-in planning.

Effects are synthesised locally with ffmpeg's lavfi sources, so the app does not
ship third-party audio assets. The placements are assembled into a single WAV
track with numpy, then mixed into the render.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from ..config import FFMPEG, SFX_DIR
from .media import run

SFX_SAMPLE_RATE = 48000


def _ensure_tone(name: str, args: list[str]) -> Path:
    path = SFX_DIR / f"{name}.wav"
    if path.exists() and path.stat().st_size > 1024:
        return path
    run(
        [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args, "-ar", str(SFX_SAMPLE_RATE), "-ac", "1", str(path)],
        timeout=120,
    )
    return path


def whoosh() -> Path:
    return _ensure_tone(
        "whoosh",
        [
            "-f",
            "lavfi",
            "-i",
            "anoisesrc=d=0.5:c=pink:r=48000:a=0.55",
            "-af",
            "highpass=f=500,lowpass=f=7000,afade=t=in:st=0:d=0.06,afade=t=out:st=0.16:d=0.34,volume=1.6",
        ],
    )


def thump() -> Path:
    return _ensure_tone(
        "thump",
        [
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=140:duration=0.3:r=48000",
            "-af",
            "afade=t=out:st=0.02:d=0.26,volume=2.2",
        ],
    )


def _read_mono(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        frames = handle.readframes(handle.getnframes())
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if handle.getnchannels() > 1:
            data = data.reshape(-1, handle.getnchannels()).mean(axis=1)
        if handle.getframerate() != SFX_SAMPLE_RATE:
            # Simple linear resample; SFX are short so this is adequate.
            ratio = SFX_SAMPLE_RATE / handle.getframerate()
            indices = np.arange(0, len(data), ratio)
            data = np.interp(indices, np.arange(len(data)), data).astype(np.float32)
    return data


def build_sfx_track(peaks: list[float], duration: float, out_path: Path, volume: float = 0.6) -> Path | None:
    """Place a whoosh + thump at each punch-in time and write one WAV file."""
    if not peaks or duration <= 0 or volume <= 0:
        return None
    whoosh_audio = _read_mono(whoosh()) * 0.55
    thump_audio = _read_mono(thump()) * 0.8
    total = int(duration * SFX_SAMPLE_RATE) + SFX_SAMPLE_RATE
    track = np.zeros(total, dtype=np.float32)

    for peak in peaks:
        start = int(max(0.0, peak - 0.18) * SFX_SAMPLE_RATE)
        end = min(total, start + len(whoosh_audio))
        if end > start:
            track[start:end] += whoosh_audio[: end - start]
        start = int(max(0.0, peak) * SFX_SAMPLE_RATE)
        end = min(total, start + len(thump_audio))
        if end > start:
            track[start:end] += thump_audio[: end - start]

    peak_value = float(np.max(np.abs(track))) or 1.0
    if peak_value > 1.0:
        track = track / peak_value
    track = np.clip(track * max(0.0, min(1.5, volume)), -1.0, 1.0)
    pcm = (track * 32767).astype(np.int16)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SFX_SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())
    return out_path
