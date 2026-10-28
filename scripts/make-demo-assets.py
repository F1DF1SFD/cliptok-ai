#!/usr/bin/env python3
"""Build the read-only sample assets used by the static demo site.

The demo has no backend, so it ships two pre-rendered projects instead of calling
the API. Those projects are produced here by the *real* pipeline (analysis,
caption grouping, reframing, FFmpeg encode) from a synthetic source clip, so the
numbers and media on the site match what the app actually emits.

    python scripts/make-demo-assets.py

Writes frontend/public/demo/ and is safe to re-run.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
WORK = ROOT / "build" / "demo-work"
OUT = ROOT / "frontend" / "public" / "demo"

# Point the app at a scratch data dir *before* importing anything that reads config.
os.environ["CLIPTOK_DATA_DIR"] = str(WORK)
sys.path.insert(0, str(BACKEND))

from app import db  # noqa: E402
from app.config import PRESETS, PROJECTS_DIR  # noqa: E402
from app.routers.projects import serialize  # noqa: E402
from app.schemas import (  # noqa: E402
    CaptionStyle,
    RenderSettings,
    Transcript,
    TranscriptSegment,
    Word,
)
from app.services import pipeline  # noqa: E402
from app.services.analyze import analyze_video  # noqa: E402
from app.services.media import FFMPEG, make_thumbnail, probe, run  # noqa: E402

DURATION = 10.0

# A short, believable stream reaction. Timings are hand-written because the demo
# has no audio worth transcribing; everything downstream (grouping, karaoke
# highlighting, render) is the app's own code.
WORDS: list[tuple[float, float, str]] = [
    (0.35, 0.62, "chat"),
    (0.62, 0.90, "said"),
    (0.90, 1.14, "this"),
    (1.14, 1.32, "was"),
    (1.32, 1.92, "impossible"),
    (2.05, 2.34, "watch"),
    (2.34, 2.58, "this"),
    (2.58, 3.02, "flank"),
    (3.15, 3.40, "nobody"),
    (3.40, 3.66, "ever"),
    (3.66, 3.94, "checks"),
    (3.94, 4.14, "it"),
    (4.42, 4.66, "oh"),
    (4.66, 4.84, "my"),
    (4.84, 5.14, "god"),
    (5.30, 5.52, "he"),
    (5.52, 5.78, "never"),
    (5.78, 6.02, "saw"),
    (6.02, 6.24, "me"),
    (6.55, 6.86, "three"),
    (6.86, 7.12, "of"),
    (7.12, 7.34, "them"),
    (7.70, 7.95, "and"),
    (7.95, 8.12, "i'm"),
    (8.12, 8.36, "still"),
    (8.36, 8.70, "alive"),
]


def build_transcript() -> Transcript:
    words = [Word(start=s, end=e, word=w) for s, e, w in WORDS]
    segments: list[TranscriptSegment] = []
    current: list[Word] = []
    for word in words:
        current.append(word)
        if word.word in {"impossible", "it", "me", "alive"}:
            segments.append(
                TranscriptSegment(
                    id=len(segments),
                    start=current[0].start,
                    end=current[-1].end,
                    text=" ".join(w.word for w in current),
                    words=list(current),
                )
            )
            current = []
    if current:
        segments.append(
            TranscriptSegment(
                id=len(segments),
                start=current[0].start,
                end=current[-1].end,
                text=" ".join(w.word for w in current),
                words=list(current),
            )
        )
    return Transcript(
        language="en",
        language_probability=0.98,
        text=" ".join(w.word for w in words),
        words=words,
        segments=segments,
        duration=DURATION,
    )


def _radial_sprite(size: int, color: tuple[int, int, int]) -> "Image.Image":
    """Soft glow blob, pre-rendered once and pasted per frame."""
    from PIL import Image

    sprite = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = sprite.load()
    half = size / 2
    for y in range(size):
        for x in range(size):
            distance = ((x - half) ** 2 + (y - half) ** 2) ** 0.5 / half
            if distance >= 1:
                continue
            alpha = int(215 * (1 - distance) ** 2.4)
            pixels[x, y] = (*color, alpha)
    return sprite


def build_source(path: Path) -> None:
    """Render a stylised top-down arena clip to stand in for gameplay footage.

    Real Twitch clips can't be redistributed, so the demo ships footage drawn
    here frame by frame: purple arena, drifting enemies, a glowing player and a
    light HUD. The audio is gated into bursts so peaks and punch-ins land on
    something the analysis can actually find.
    """
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    width, height, fps = 1280, 720, 30
    frames = WORK / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True, exist_ok=True)

    font_path = BACKEND / "app" / "assets" / "fonts" / "ArchivoBlack-Regular.ttf"
    hud_font = ImageFont.truetype(str(font_path), 20)
    hud_small = ImageFont.truetype(str(font_path), 15)

    # Static background: vertical gradient, arena plate, grid, vignette.
    backdrop = Image.new("RGB", (width, height), (11, 7, 20))
    draw = ImageDraw.Draw(backdrop)
    for y in range(height):
        blend = y / height
        draw.line(
            [(0, y), (width, y)],
            fill=(int(11 + blend * 12), int(7 + blend * 4), int(20 + blend * 22)),
        )
    arena = (28, 20, width - 28, height - 20)
    draw.rounded_rectangle(arena, radius=26, fill=(18, 11, 32), outline=(145, 70, 255, 60), width=2)
    for gx in range(arena[0] + 64, arena[2], 64):
        draw.line([(gx, arena[1] + 8), (gx, arena[3] - 8)], fill=(38, 26, 62), width=1)
    for gy in range(arena[1] + 64, arena[3], 64):
        draw.line([(arena[0] + 8, gy), (arena[2] - 8, gy)], fill=(38, 26, 62), width=1)

    vignette = Image.new("L", (width, height), 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse((-220, -260, width + 220, height + 260), fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(150))
    dark = Image.new("RGB", (width, height), (4, 2, 9))
    backdrop = Image.composite(backdrop, dark, vignette)

    scanlines = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(scanlines)
    for y in range(0, height, 3):
        sdraw.line([(0, y), (width, y)], fill=(0, 0, 0, 26))

    glow_purple = _radial_sprite(240, (145, 70, 255))
    glow_red = _radial_sprite(200, (255, 78, 96))
    glow_white = _radial_sprite(160, (255, 255, 255))

    peaks = [(2.5, 3.2), (4.4, 5.2), (7.6, 8.7)]
    total = int(DURATION * fps)
    for index in range(total):
        t = index / fps
        shake = 0.0
        for start, end in peaks:
            if start <= t <= end:
                shake = 7.0
        camera_x = 14 * math.sin(t * 0.42) + (math.sin(t * 77) * shake if shake else 0)
        camera_y = 10 * math.cos(t * 0.31) + (math.cos(t * 91) * shake if shake else 0)

        frame = backdrop.copy()
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        enemies = [
            (560 + 210 * math.sin(t * 0.85 + 0.4), 300 + 130 * math.cos(t * 0.72)),
            (760 + 170 * math.sin(t * 0.61 + 2.1), 460 + 110 * math.sin(t * 0.9 + 1.2)),
            (430 + 150 * math.cos(t * 0.54 + 1.1), 520 + 90 * math.sin(t * 0.66 + 0.3)),
        ]
        for ex, ey in enemies:
            layer.alpha_composite(glow_red, (int(ex - 100), int(ey - 100)))
            ImageDraw.Draw(layer).ellipse((ex - 11, ey - 11, ex + 11, ey + 11), fill=(255, 92, 108, 255))

        px = 640 + 250 * math.sin(t * 0.53)
        py = 380 + 140 * math.sin(t * 0.79 + 0.9)
        for trail in range(1, 9):
            past = max(0.0, t - trail * 0.045)
            tx = 640 + 250 * math.sin(past * 0.53)
            ty = 380 + 140 * math.sin(past * 0.79 + 0.9)
            alpha = int(120 * (1 - trail / 9))
            ImageDraw.Draw(layer).ellipse((tx - 7, ty - 7, tx + 7, ty + 7), fill=(145, 70, 255, alpha))
        layer.alpha_composite(glow_purple, (int(px - 120), int(py - 120)))
        ImageDraw.Draw(layer).ellipse((px - 13, py - 13, px + 13, py + 13), fill=(226, 208, 255, 255))

        # Crosshair sweeps ahead of the player.
        cx = px + 96 * math.cos(t * 1.1)
        cy = py + 54 * math.sin(t * 1.1)
        cross = ImageDraw.Draw(layer)
        cross.line([(cx - 14, cy), (cx - 4, cy)], fill=(255, 255, 255, 190), width=2)
        cross.line([(cx + 4, cy), (cx + 14, cy)], fill=(255, 255, 255, 190), width=2)
        cross.line([(cx, cy - 14), (cx, cy - 4)], fill=(255, 255, 255, 190), width=2)
        cross.line([(cx, cy + 4), (cx, cy + 14)], fill=(255, 255, 255, 190), width=2)

        if shake:
            layer.alpha_composite(glow_white, (int(px - 80), int(py - 80)))

        frame = frame.copy()
        frame.paste(
            layer,
            (int(round(camera_x)), int(round(camera_y))),
            layer,
        )
        frame = Image.alpha_composite(frame.convert("RGBA"), scanlines).convert("RGB")

        # Webcam mock in the bottom-left. The facecam-split render crops this
        # exact box (analysis.facecam is in source pixels), so it draws on its
        # own canvas and is pasted back to stay inside the frame.
        cam = Image.new("RGBA", (300, 220), (0, 0, 0, 0))
        cam_draw = ImageDraw.Draw(cam)
        cam_draw.rounded_rectangle((0, 0, 299, 219), radius=18, fill=(24, 15, 44, 255))
        pulse = 0.5 + 0.5 * math.sin(t * 2.4)
        cam.alpha_composite(glow_purple, (int(30 + 12 * math.sin(t * 1.7)), int(-20 + 10 * math.cos(t * 1.3))))
        cam_draw.ellipse((40, 138, 260, 300), fill=(52, 38, 88, 255))
        cam_draw.ellipse((72, 52, 148, 128), fill=(74, 56, 116, 255))
        cam_draw.ellipse((84, 64, 136, 116), fill=(104, 82, 152, int(150 + 90 * pulse)))
        cam_draw.rounded_rectangle((0, 0, 299, 219), radius=18, outline=(145, 70, 255, 130), width=2)
        cam_draw.text((12, 194), "CAM", font=hud_small, fill=(160, 142, 200))
        frame = frame.convert("RGBA")
        frame.paste(cam, (40, 470), cam)
        frame = frame.convert("RGB")

        hud = ImageDraw.Draw(frame)
        hud.text((56, 46), "ASCENT  ·  ROUND 7", font=hud_small, fill=(138, 124, 168))
        hud.text((width - 152, 44), "02:14", font=hud_font, fill=(226, 214, 248))
        hud.rounded_rectangle((width - 330, height - 60, width - 130, height - 48), radius=6,
                             fill=(45, 30, 74))
        hud.rounded_rectangle((width - 330, height - 60, width - 152, height - 48), radius=6,
                             fill=(145, 70, 255))
        hud.text((width - 118, height - 68), "HP 88", font=hud_small, fill=(150, 136, 180))

        frame.save(frames / f"{index:04d}.png")

    audio = (
        "[1:a]volume='if(between(t,2.5,3.2)+between(t,4.4,5.2)+between(t,7.6,8.7),1.0,0.12)'"
        ":eval=frame,aformat=channel_layouts=stereo[a]"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames / "%04d.png"),
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=170:duration={DURATION}",
            "-filter_complex",
            audio,
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-t",
            str(DURATION),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "26",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(path),
        ],
        timeout=600,
    )


def make_project(
    *,
    source_video: Path,
    name: str,
    source_url: str | None,
    settings: RenderSettings,
    analysis: dict,
    transcript: Transcript,
) -> dict:
    info = probe(source_video)
    project = db.create_project(
        name=name,
        source_kind="twitch" if source_url else "upload",
        source_url=source_url,
        duration=info.duration,
        width=info.width,
        height=info.height,
    )
    project_id = project["id"]

    source = pipeline.source_file(project)
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_video, source)

    thumb = PROJECTS_DIR / project_id / "thumbnail.jpg"
    make_thumbnail(source, thumb, 3.0)

    db.update_project(
        project_id,
        settings=settings,
        data_patch={
            "files": {"source": "source.mp4"},
            "thumbnail": "thumbnail.jpg",
            "transcript": transcript.model_dump(),
            "analysis": analysis,
        },
    )
    return db.get_project(project_id) or project


def variant_a() -> tuple[dict, RenderSettings]:
    settings = RenderSettings()
    settings.preset = "tiktok"
    settings.captions = CaptionStyle(
        font_size=88,
        words_per_line=3,
        position_y=0.72,
        active_color="#FFE600",
        outline_width=6,
    )
    settings.effects.punch_ins = True
    settings.effects.punch_in_count = 4
    settings.effects.sfx = False
    settings.effects.saturation = 1.1
    settings.trim.start = 0.2
    settings.trim.end = 9.2
    settings.overlays = []
    return (
        {
            "name": "Clutch 1v3 on Ascent",
            "source_url": "https://clips.twitch.tv/FancyClutchSlug",
        },
        settings,
    )


def variant_b() -> tuple[dict, RenderSettings]:
    settings = RenderSettings()
    settings.preset = "reels"
    settings.captions = CaptionStyle(
        font_size=94,
        words_per_line=4,
        position_y=0.80,
        active_color="#39FF88",
        outline_width=5,
    )
    settings.reframe.facecam_split = True
    settings.reframe.facecam_height = 620
    settings.reframe.focus = "face"
    settings.effects.punch_ins = True
    settings.effects.punch_in_count = 3
    settings.effects.sfx = False
    settings.effects.flash = False
    settings.trim.start = 0.0
    settings.trim.end = 9.0
    return (
        {"name": "Chat went feral", "source_url": None},
        settings,
    )


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    db.init_db()

    source_video = PROJECTS_DIR / "sample_source" / "source.mp4"
    build_source(source_video)
    info = probe(source_video)
    transcript = build_transcript()

    print(f"source: {info.width}x{info.height} {info.duration:.1f}s")

    # One real analysis pass; the facecam variant reuses it with a synthetic box
    # (the fractal has no webcam) so the split layout can be demonstrated.
    analysis = analyze_video(source_video, focus="action", smoothing=0.45)
    analysis["focus"] = "action"
    facecam = {"x": 40.0, "y": 470.0, "w": 300.0, "h": 220.0, "coverage": 0.9, "area_ratio": 0.0716}
    facecam_analysis = dict(analysis)
    facecam_analysis["facecam"] = facecam
    facecam_analysis["focus"] = "face"
    facecam_analysis["facecam_detected"] = True

    projects = []
    for builder, analysis_doc, label in (
        (variant_a, analysis, "clutch-1v3"),
        (variant_b, facecam_analysis, "chat-feral"),
    ):
        meta, settings = builder()
        project = make_project(
            source_video=source_video,
            name=meta["name"],
            source_url=meta["source_url"],
            settings=settings,
            analysis=analysis_doc,
            transcript=transcript,
        )
        print(f"rendering {meta['name']} ...")
        pipeline.render(project["id"], "preview", lambda value, message: None)
        project = db.get_project(project["id"]) or project

        payload = serialize(project)
        project_id = payload["id"]
        # Stable slug so editor URLs never change between rebuilds.
        payload["id"] = label
        target = OUT / label
        target.mkdir(parents=True, exist_ok=True)
        for relative in ["thumbnail.jpg", "renders/preview.mp4", "renders/preview.jpg"]:
            candidate = PROJECTS_DIR / project_id / relative
            if candidate.exists():
                (target / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(candidate, target / relative)

        prefix = f"/api/media/{project_id}/"

        def rewrite(url: str | None) -> str | None:
            if not url or not url.startswith(prefix):
                return url
            return f"/demo/{label}/" + url[len(prefix) :].split("?")[0]

        payload["urls"] = {key: rewrite(value) for key, value in payload["urls"].items()}
        # One shared copy of the sample footage instead of one per project.
        payload["urls"]["source"] = "/demo/source.mp4"
        payload.pop("active_job", None)
        payload["active_job"] = None
        projects.append(payload)
        print(f"  -> {payload['renders']['preview']['width']}x"
              f"{payload['renders']['preview']['height']} "
              f"{payload['renders']['preview']['size_bytes'] / 1024:.0f} KiB, "
              f"{payload['renders']['preview']['punch_ins']} punch-ins, "
              f"{len(payload['caption_lines'])} caption lines")

    shutil.copyfile(source_video, OUT / "source.mp4")

    share = {
        "slug": "demo-clutch",
        "title": projects[0]["name"],
        "quality": "preview",
        "duration": projects[0]["renders"]["preview"]["duration"],
        "width": projects[0]["renders"]["preview"]["width"],
        "height": projects[0]["renders"]["preview"]["height"],
        "preset": projects[0]["renders"]["preview"]["preset"],
        "captions": True,
        "source_kind": "twitch",
        "published_at": projects[0]["updated_at"],
        "video_url": projects[0]["urls"]["preview"],
        "thumbnail_url": projects[0]["urls"]["preview_thumbnail"],
        "download_url": projects[0]["urls"]["preview"],
    }

    health = {
        "status": "ok",
        "capabilities": {
            "ffmpeg": True,
            "ffprobe": True,
            "ytdlp": True,
            "whisper": True,
            "opencv": True,
        },
        "whisper_model": "base",
        "limits": {"max_upload_bytes": 512 * 1024 * 1024, "max_clip_seconds": 600},
        "presets": [
            {
                "id": key,
                "label": value["label"],
                "width": value["width"],
                "height": value["height"],
                "fps": value["fps"],
                "video_bitrate": value["video_bitrate"],
                "description": value["description"],
            }
            for key, value in PRESETS.items()
        ],
        "fonts": ["Arial Black", "Impact", "Arial Bold", "Arial Rounded Bold"],
    }

    stickers = []
    emoji_dir = BACKEND / "app" / "assets" / "emoji"
    sticker_out = OUT / "stickers"
    if sticker_out.exists():
        shutil.rmtree(sticker_out)
    sticker_out.mkdir(parents=True, exist_ok=True)
    for png in sorted(emoji_dir.glob("*.png")):
        shutil.copyfile(png, sticker_out / png.name)
        stickers.append({"id": png.stem, "url": f"/demo/stickers/{png.name}"})

    bundle = {
        "generated_at": projects[0]["updated_at"],
        "projects": projects,
        "share": share,
        "health": health,
        "stickers": stickers,
    }
    (OUT / "demo-data.json").write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    total = sum(path.stat().st_size for path in OUT.rglob("*") if path.is_file())
    print(f"wrote {OUT} ({total / 1024 / 1024:.1f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
