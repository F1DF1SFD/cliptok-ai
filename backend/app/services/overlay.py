"""Rasterise captions and stickers into a transparent overlay track.

The local FFmpeg is a minimal static build without libass/freetype, so instead
of burning ASS we draw every overlay state with Pillow and feed the resulting
PNGs to FFmpeg through the concat demuxer. One overlay pass then composites the
whole track on top of the reframed video.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont

from ..schemas import CaptionStyle, Overlay, RenderSettings, Transcript
from .captions import CaptionRun, caption_runs, hex_to_rgba

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
EMOJI_DIR = ASSET_DIR / "emoji"
FONT_DIR = ASSET_DIR / "fonts"
DEFAULT_OVERLAY_FONT = "Arial Black"

# Shipped with the app (SIL OFL, see assets/fonts/OFL.txt) so captions render on
# any machine, including Windows installs without the Arial/Impact families.
BUNDLED_FONT = FONT_DIR / "ArchivoBlack-Regular.ttf"

MAC_FONTS = Path("/System/Library/Fonts/Supplemental")
WIN_FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
LINUX_FONT_DIRS = [
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/TTF"),
]


def _first_existing(*candidates: Path) -> str:
    """First font file that exists on this machine (bundled font otherwise)."""
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    for directory in LINUX_FONT_DIRS:
        for pattern in ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"):
            found = directory / pattern
            if found.exists():
                return str(found)
    return str(BUNDLED_FONT)


def resolve_font_files(
    mac_dir: Path = MAC_FONTS, win_dir: Path = WIN_FONTS
) -> dict[str, str]:
    """Map each caption face to a real font file for this platform.

    The same four names are offered everywhere so a project looks the same on
    macOS and Windows. Windows filenames are the 8.3-style Fonts directory
    names (``ariblk.ttf``, ``impact.ttf``); Segoe UI is tried after Arial
    because stripped Windows images ship Segoe UI even without Arial Black.
    """
    return {
        "Arial Black": _first_existing(
            mac_dir / "Arial Black.ttf",
            win_dir / "ariblk.ttf",
            win_dir / "seguibl.ttf",
            win_dir / "segoeuib.ttf",
            win_dir / "arialbd.ttf",
        ),
        "Impact": _first_existing(
            mac_dir / "Impact.ttf",
            win_dir / "impact.ttf",
            win_dir / "ariblk.ttf",
            win_dir / "seguibl.ttf",
            win_dir / "arialbd.ttf",
        ),
        "Arial Bold": _first_existing(
            mac_dir / "Arial Bold.ttf",
            win_dir / "arialbd.ttf",
            win_dir / "segoeuib.ttf",
        ),
        "Arial Rounded Bold": _first_existing(
            mac_dir / "Arial Rounded Bold.ttf",
            win_dir / "ariblk.ttf",
            win_dir / "arialbd.ttf",
            win_dir / "segoeuib.ttf",
        ),
    }


def fallback_fonts(
    mac_dir: Path = MAC_FONTS, win_dir: Path = WIN_FONTS
) -> list[str]:
    """Ordered font files to try when a project names a face we cannot resolve."""
    resolved = resolve_font_files(mac_dir, win_dir)
    return [
        resolved["Arial Black"],
        resolved["Arial Bold"],
        str(mac_dir / "Arial Black.ttf"),
        str(win_dir / "ariblk.ttf"),
        str(win_dir / "segoeuib.ttf"),
        str(win_dir / "arialbd.ttf"),
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        str(BUNDLED_FONT),
    ]


FONT_FILES: dict[str, str] = resolve_font_files()
FALLBACK_FONTS = fallback_fonts()

POP_STEPS = ((0.0, 0.075, 0.86), (0.075, 0.155, 1.1))

ProgressFn = Callable[[float, str], None]


def available_fonts() -> list[str]:
    return [name for name, path in FONT_FILES.items() if Path(path).exists()]


def font_path(name: str) -> str:
    candidate = FONT_FILES.get(name)
    if candidate and Path(candidate).exists():
        return candidate
    for fallback in FALLBACK_FONTS:
        if Path(fallback).exists():
            return fallback
    raise RuntimeError("No usable font found for caption rendering")


def sticker_ids() -> list[str]:
    if not EMOJI_DIR.exists():
        return []
    return sorted(path.stem for path in EMOJI_DIR.glob("*.png"))


def sticker_path(sticker_id: str) -> Optional[Path]:
    safe = "".join(ch for ch in (sticker_id or "") if ch.isalnum() or ch in "-_")
    if not safe:
        return None
    path = EMOJI_DIR / f"{safe.lower()}.png"
    return path if path.is_file() else None


@lru_cache(maxsize=256)
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path(name), max(8, size))


def _draw_caption(
    image: Image.Image,
    run: CaptionRun,
    style: CaptionStyle,
    width: int,
    height: int,
    time_in_run: float,
) -> None:
    scale = height / 1920.0
    font_size = max(10.0, style.font_size * scale)
    base_size = int(round(font_size))
    font = _font(style.font, base_size)
    draw = ImageDraw.Draw(image)
    spacing = font_size * 0.24
    max_width = width * 0.9

    active_scale = 1.0
    if style.pop_in:
        for start, end, value in POP_STEPS:
            if start <= time_in_run < end:
                active_scale = value
                break
    active_font = _font(style.font, int(round(font_size * active_scale))) if active_scale != 1.0 else font

    widths = [float(draw.textlength(word, font=font)) + spacing for word in run.words]

    rows: list[list[tuple[str, int, float]]] = []
    row: list[tuple[str, int, float]] = []
    row_width = 0.0
    for index, word in enumerate(run.words):
        if row and row_width + widths[index] > max_width:
            rows.append(row)
            row = []
            row_width = 0.0
        row.append((word, index, widths[index]))
        row_width += widths[index]
    if row:
        rows.append(row)

    ascent, descent = font.getmetrics()
    line_height = (ascent + descent) * 1.12
    block_height = line_height * len(rows)
    top = style.position_y * height - block_height / 2
    text_color = hex_to_rgba(style.text_color)
    active_color = hex_to_rgba(style.active_color)
    outline = int(round(style.outline_width * scale * 1.5))
    outline_color = hex_to_rgba(style.outline_color)

    if style.background:
        widest = max((sum(w for _, _, w in r) - spacing for r in rows), default=0)
        padding = font_size * 0.28
        draw.rounded_rectangle(
            (
                width / 2 - widest / 2 - padding,
                top - padding,
                width / 2 + widest / 2 + padding,
                top + block_height + padding,
            ),
            radius=int(font_size * 0.22),
            fill=hex_to_rgba(style.background_color, 235),
        )

    for row_index, current_row in enumerate(rows):
        total = sum(w for _, _, w in current_row) - spacing
        x = (width - total) / 2
        baseline = top + row_index * line_height + ascent
        for word, index, word_width in current_row:
            is_active = index == run.active
            draw.text(
                (x + word_width / 2, baseline),
                word,
                font=active_font if is_active else font,
                anchor="ms",
                fill=active_color if is_active else text_color,
                stroke_width=outline,
                stroke_fill=outline_color,
            )
            x += word_width


def _pop_scale(elapsed: float, first: float = 0.09, second: float = 0.18) -> float:
    if elapsed < first:
        return 0.82
    if elapsed < second:
        return 1.06
    return 1.0


def _draw_text_overlay(
    image: Image.Image, overlay: Overlay, width: int, height: int, elapsed: float
) -> None:
    scale = height / 1920.0
    size = max(12.0, overlay.size * scale * _pop_scale(elapsed))
    font = _font(DEFAULT_OVERLAY_FONT, int(round(size)))
    draw = ImageDraw.Draw(image)
    draw.text(
        (max(0.0, min(1.0, overlay.x)) * width, max(0.0, min(1.0, overlay.y)) * height),
        overlay.text,
        font=font,
        anchor="mm",
        fill=hex_to_rgba(overlay.color),
        stroke_width=max(2, int(7 * scale)),
        stroke_fill=(0, 0, 0, 255),
    )


def _draw_sticker(
    image: Image.Image, overlay: Overlay, width: int, height: int, elapsed: float
) -> None:
    path = sticker_path(overlay.text)
    if not path:
        _draw_text_overlay(image, overlay, width, height, elapsed)
        return
    scale = height / 1920.0
    base = max(28.0, overlay.size * scale * 1.8)
    size = max(16, int(round(base * _pop_scale(elapsed, 0.1, 0.2))))
    sticker = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
    x = max(0.0, min(1.0, overlay.x)) * width
    y = max(0.0, min(1.0, overlay.y)) * height
    image.alpha_composite(sticker, (int(x - size / 2), int(y - size / 2)))


def _boundaries(
    runs: list[CaptionRun], overlays: list[Overlay], duration: float, detailed: bool
) -> list[float]:
    points: set[float] = {0.0, max(0.0, duration)}

    def add(value: float) -> None:
        points.add(round(max(0.0, min(duration, value)), 3))

    for run in runs:
        add(run.start)
        add(run.end)
        if detailed:
            add(run.start + 0.075)
            add(run.start + 0.155)
    for overlay in overlays:
        add(overlay.start)
        add(overlay.end)
        if detailed:
            add(overlay.start + 0.09)
            add(overlay.start + 0.18)
    return sorted(points)


def _shift_runs(runs: list[CaptionRun], offset: float, duration: float) -> list[CaptionRun]:
    shifted: list[CaptionRun] = []
    for run in runs:
        start = max(0.0, run.start - offset)
        end = min(duration, run.end - offset)
        if end <= start or end <= 0 or start >= duration:
            continue
        shifted.append(
            CaptionRun(
                start=start,
                end=end,
                words=run.words,
                starts=[value - offset for value in run.starts],
                ends=[value - offset for value in run.ends],
                active=run.active,
            )
        )
    return shifted


def _shift_overlays(overlays: list[Overlay], offset: float, duration: float) -> list[Overlay]:
    shifted: list[Overlay] = []
    for overlay in overlays:
        start = max(0.0, overlay.start - offset)
        end = min(duration, overlay.end - offset)
        if end <= start:
            continue
        shifted.append(overlay.model_copy(update={"start": start, "end": end}))
    return shifted


def build_overlay_track(
    *,
    transcript: Optional[Transcript],
    settings: RenderSettings,
    width: int,
    height: int,
    duration: float,
    out_dir: Path,
    time_offset: float = 0.0,
    progress: Optional[ProgressFn] = None,
) -> Optional[Path]:
    """Render all caption/sticker states and return a concat-demuxer script.

    ``time_offset`` is the trim start: project times are absolute in the source
    video, while the rendered clip starts at zero.
    """
    style = settings.captions
    runs: list[CaptionRun] = (
        caption_runs(transcript, style) if style.enabled and transcript else []
    )
    overlays = [o for o in settings.overlays if o.text.strip() and o.end > o.start]
    if time_offset:
        runs = _shift_runs(runs, time_offset, duration)
        overlays = _shift_overlays(overlays, time_offset, duration)
    if not runs and not overlays or duration <= 0:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.png"):
        stale.unlink(missing_ok=True)

    points = _boundaries(runs, overlays, duration, detailed=True)
    intervals = [
        (points[i], points[i + 1])
        for i in range(len(points) - 1)
        if points[i + 1] - points[i] > 0.001
    ]
    if not intervals:
        return None
    if len(intervals) > 500:
        points = _boundaries(runs, overlays, duration, detailed=False)
        intervals = [
            (points[i], points[i + 1])
            for i in range(len(points) - 1)
            if points[i + 1] - points[i] > 0.001
        ]

    lines: list[str] = []
    frame_index = 0
    total = len(intervals)
    last_was_blank = False
    for index, (start, end) in enumerate(intervals):
        active_runs = [r for r in runs if r.start <= start < r.end]
        active_overlays = [o for o in overlays if o.start <= start < o.end]
        if not active_runs and not active_overlays:
            if last_was_blank and lines:
                # Merge consecutive empty gaps into the previous transparent frame.
                previous = float(lines[-1].split(" ", 1)[1])
                lines[-1] = f"duration {previous + (end - start):.3f}"
                continue

        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for run in active_runs:
            _draw_caption(canvas, run, style, width, height, start - run.start)
        for overlay in active_overlays:
            if overlay.kind == "emoji":
                _draw_sticker(canvas, overlay, width, height, start - overlay.start)
            else:
                _draw_text_overlay(canvas, overlay, width, height, start - overlay.start)

        frame_path = out_dir / f"f{frame_index:04d}.png"
        canvas.save(frame_path, optimize=True)
        frame_index += 1
        lines.append(f"file '{frame_path.name}'")
        lines.append(f"duration {max(0.02, end - start):.3f}")
        last_was_blank = not active_runs and not active_overlays
        if progress and index % 8 == 0:
            progress(0.6 + 0.15 * (index / max(1, total)), "Rendering caption frames")

    if not lines:
        return None
    last = [line for line in lines if line.startswith("file ")][-1].split("'")[1]
    lines.append(f"file '{last}'")
    script = out_dir / "overlay.txt"
    script.write_text("\n".join(lines) + "\n")
    return script
