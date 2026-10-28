import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageFont

from app.schemas import CaptionStyle, Overlay, RenderSettings, Transcript, Word
from app.services import overlay as overlay_mod
from app.services.overlay import (
    BUNDLED_FONT,
    build_overlay_track,
    fallback_fonts,
    resolve_font_files,
    sticker_ids,
)


def transcript_three_words() -> Transcript:
    words = [
        Word(start=0.2, end=0.6, word="this"),
        Word(start=0.6, end=1.0, word="is"),
        Word(start=1.0, end=1.4, word="clutch"),
    ]
    return Transcript(language="en", text="this is clutch", words=words, duration=2.0)


def read_script(script: Path) -> list[str]:
    return [line.strip() for line in script.read_text().splitlines() if line.strip()]


def test_overlay_track_covers_the_whole_timeline(tmp_path: Path):
    settings = RenderSettings()
    settings.captions = CaptionStyle(font_size=90, words_per_line=3)
    script = build_overlay_track(
        transcript=transcript_three_words(),
        settings=settings,
        width=540,
        height=960,
        duration=2.0,
        out_dir=tmp_path,
    )
    assert script is not None
    lines = read_script(script)
    durations = [float(line.split(" ")[1]) for line in lines if line.startswith("duration ")]
    assert abs(sum(durations) - 2.0) < 0.05
    assert len(list(tmp_path.glob("*.png"))) > 0


def test_caption_frame_contains_text_pixels(tmp_path: Path):
    settings = RenderSettings()
    settings.captions = CaptionStyle(font_size=100, words_per_line=3)
    build_overlay_track(
        transcript=transcript_three_words(),
        settings=settings,
        width=540,
        height=960,
        duration=2.0,
        out_dir=tmp_path,
    )
    frames = sorted(tmp_path.glob("*.png"))
    # The first non-empty frame should paint the caption block around 74% height.
    painted = None
    for frame in frames:
        image = np.array(Image.open(frame).convert("RGBA"))
        alpha = image[:, :, 3]
        if alpha.sum() > 0:
            painted = alpha
            break
    assert painted is not None
    rows = np.where(painted.sum(axis=1) > 0)[0]
    assert rows.min() > 400
    assert rows.min() < 900


def test_overlay_track_shifts_for_trimmed_clips(tmp_path: Path):
    settings = RenderSettings()
    settings.captions = CaptionStyle(font_size=90, words_per_line=3)
    script = build_overlay_track(
        transcript=transcript_three_words(),
        settings=settings,
        width=540,
        height=960,
        duration=2.0,
        out_dir=tmp_path,
        time_offset=0.5,
    )
    assert script is not None
    lines = read_script(script)
    first_duration = float(lines[1].split(" ")[1])
    # First frame is transparent up to the shifted start of the first caption (0.2 - 0.5 < 0).
    assert first_duration > 0
    assert lines[0].startswith("file ")


def test_stickers_are_bundled():
    ids = sticker_ids()
    assert "fire" in ids and len(ids) > 20


def fake_font_dirs(tmp_path: Path, windows_names: list[str]) -> tuple[Path, Path]:
    """A macOS-less machine with a Windows Fonts directory holding given files."""
    mac_dir = tmp_path / "Supplemental"
    win_dir = tmp_path / "Windows" / "Fonts"
    mac_dir.mkdir(parents=True)
    win_dir.mkdir(parents=True)
    for name in windows_names:
        shutil.copyfile(BUNDLED_FONT, win_dir / name)
    return mac_dir, win_dir


def test_windows_font_names_resolve_to_windows_files(tmp_path: Path):
    mac_dir, win_dir = fake_font_dirs(tmp_path, ["ariblk.ttf", "impact.ttf", "arialbd.ttf"])
    fonts = resolve_font_files(mac_dir, win_dir)

    assert fonts["Arial Black"] == str(win_dir / "ariblk.ttf")
    assert fonts["Impact"] == str(win_dir / "impact.ttf")
    assert fonts["Arial Bold"] == str(win_dir / "arialbd.ttf")
    assert fonts["Arial Rounded Bold"] == str(win_dir / "ariblk.ttf")
    # Every mapped file must be loadable by Pillow on that machine.
    for path in fonts.values():
        ImageFont.truetype(path, 40)


def test_stripped_windows_falls_back_to_segoe(tmp_path: Path):
    mac_dir, win_dir = fake_font_dirs(tmp_path, ["seguibl.ttf", "segoeuib.ttf"])
    fonts = resolve_font_files(mac_dir, win_dir)

    assert fonts["Arial Black"] == str(win_dir / "seguibl.ttf")
    assert fonts["Impact"] == str(win_dir / "seguibl.ttf")
    assert fonts["Arial Bold"] == str(win_dir / "segoeuib.ttf")


def test_missing_system_fonts_use_the_bundled_font(tmp_path: Path):
    mac_dir, win_dir = fake_font_dirs(tmp_path, [])
    fonts = resolve_font_files(mac_dir, win_dir)

    assert BUNDLED_FONT.exists(), "captions must ship their own font"
    assert set(fonts.values()) == {str(BUNDLED_FONT)}
    assert fallback_fonts(mac_dir, win_dir)[-1] == str(BUNDLED_FONT)
    ImageFont.truetype(str(BUNDLED_FONT), 40)


def test_captions_render_without_any_system_font(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A Windows box with no Arial/Impact still burns readable captions."""
    mac_dir, win_dir = fake_font_dirs(tmp_path, ["segoeuib.ttf"])
    monkeypatch.setattr(overlay_mod, "FONT_FILES", resolve_font_files(mac_dir, win_dir))
    monkeypatch.setattr(overlay_mod, "FALLBACK_FONTS", fallback_fonts(mac_dir, win_dir))
    overlay_mod._font.cache_clear()

    settings = RenderSettings()
    settings.captions = CaptionStyle(font_size=100, words_per_line=3)
    script = build_overlay_track(
        transcript=transcript_three_words(),
        settings=settings,
        width=540,
        height=960,
        duration=2.0,
        out_dir=tmp_path / "overlay",
    )
    overlay_mod._font.cache_clear()

    assert script is not None
    pixels = np.concatenate(
        [np.array(Image.open(frame).convert("RGBA")) for frame in sorted(script.parent.glob("*.png"))]
    )
    opaque = pixels[pixels[:, :, 3] > 200][:, :3]
    assert len(opaque) > 1000, "caption text should be painted"
    # White body text and the yellow active word both survive the fallback font.
    assert (opaque[:, :3].min(axis=1) > 230).any()
    assert ((opaque[:, 0] > 230) & (opaque[:, 1] > 190) & (opaque[:, 2] < 90)).any()


def test_emoji_overlay_is_drawn(tmp_path: Path):
    settings = RenderSettings()
    settings.captions = CaptionStyle(enabled=False)
    settings.overlays = [
        Overlay(id="a", kind="emoji", text="fire", start=0.0, end=1.0, x=0.5, y=0.5, size=120)
    ]
    script = build_overlay_track(
        transcript=None,
        settings=settings,
        width=540,
        height=960,
        duration=1.0,
        out_dir=tmp_path,
    )
    assert script is not None
    frame = sorted(tmp_path.glob("*.png"))[0]
    alpha = np.array(Image.open(frame).convert("RGBA"))[:, :, 3]
    assert alpha.sum() > 0
