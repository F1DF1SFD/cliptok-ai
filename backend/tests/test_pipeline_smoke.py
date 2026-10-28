"""End-to-end FFmpeg smoke test (skipped when FFmpeg is unavailable)."""

from pathlib import Path

import pytest

from app.schemas import CaptionStyle, RenderSettings, Transcript, TranscriptSegment, Word
from app.services.media import FFMPEG, MediaError, ffmpeg_available, probe
from app.services.render import render_project


pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not installed")


def make_clip(path: Path, seconds: int = 2) -> None:
    from app.services.media import run

    run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=640x360:rate=30:duration={seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        timeout=120,
    )


def test_render_smoke_produces_vertical_captioned_clip(tmp_path: Path):
    source = tmp_path / "source.mp4"
    make_clip(source, seconds=2)

    words = [
        Word(start=0.2, end=0.6, word="hello"),
        Word(start=0.6, end=1.0, word="world"),
    ]
    transcript = Transcript(
        language="en",
        text="hello world",
        words=words,
        segments=[TranscriptSegment(id=0, start=0.2, end=1.0, text="hello world", words=words)],
        duration=2.0,
    )
    settings = RenderSettings()
    settings.captions = CaptionStyle(font_size=90, words_per_line=2)
    settings.effects.punch_ins = False
    settings.effects.sfx = False
    project = {"id": "smoke", "settings": settings.model_dump()}
    analysis = {
        "width": 640,
        "height": 360,
        "duration": 2.0,
        "fps": 30,
        "has_audio": True,
        "facecam": None,
        "trajectory": [[0.0, 0.5], [2.0, 0.5]],
        "peaks": [],
        "energy": [],
    }

    output = tmp_path / "out.mp4"
    result = render_project(
        project=project,
        source=source,
        quality="preview",
        out_path=output,
        work_dir=tmp_path / "work",
        analysis=analysis,
        transcript=transcript,
        music=None,
    )

    assert output.exists()
    info = probe(output)
    assert (info.width, info.height) == (540, 960)
    assert 1.5 < info.duration < 2.5
    assert result["captions"] is True
    assert result["punch_ins"] == 0
