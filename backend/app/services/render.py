"""The render pipeline: reframe -> punch-ins -> captions/overlays/audio.

Three FFmpeg passes are used so every stage stays inspectable and cache-free:

1. ``reframe``  - trim, tracked 9:16 crop (or gameplay + facecam stack), audio.
2. ``punch``    - snap zooms on loud moments, built from concat segments.
3. ``composite``- ASS captions/overlays, colour, flashes, music + SFX mix.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Optional

from ..config import FFMPEG, PRESETS
from ..schemas import RenderSettings, Transcript
from . import analyze as analyze_mod
from .effects import build_sfx_track
from .media import MediaInfo, probe, run
from .overlay import build_overlay_track

ProgressFn = Callable[[float, str], None]


def _even(value: float) -> int:
    """Round to an even pixel value (0 allowed for crop offsets)."""
    return int(round(value)) // 2 * 2


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def filter_escape(path: Path) -> str:
    """Escape a filesystem path for use inside an FFmpeg filtergraph."""
    pieces: list[str] = []
    for char in str(path).replace("\\", "/"):
        if char in "\\':,[]; ":
            pieces.append("\\")
        pieces.append(char)
    return "".join(pieces)


def target_size(settings: RenderSettings, quality: str) -> tuple[int, int]:
    preset = PRESETS[settings.preset]
    width, height = preset["width"], preset["height"]
    if quality == "preview":
        width, height = width // 2, height // 2
    return _even(width), _even(height)


def cover_crop(src_w: int, src_h: int, out_w: int, out_h: int) -> tuple[int, int]:
    """Largest out-ratio crop that fits inside the source."""
    target = out_w / out_h
    if src_w / src_h > target:
        crop_h = src_h
        crop_w = src_h * target
    else:
        crop_w = src_w
        crop_h = src_w / target
    crop_w = max(2, min(_even(crop_w), _even(src_w)))
    crop_h = max(2, min(_even(crop_h), _even(src_h)))
    return crop_w, crop_h


def _crop_x(analysis: dict, time_abs: float, src_w: int, crop_w: int, focus: str) -> int:
    if focus == "center":
        center = 0.5
    else:
        center = analyze_mod.principal_center(analysis, time_abs)
    return _even(_clamp(center * src_w - crop_w / 2, 0, max(0, src_w - crop_w)))


def build_sendcmd(
    analysis: dict,
    *,
    src_w: int,
    crop_w: int,
    trim_start: float,
    trim_end: float,
    focus: str = "action",
    step: float = 0.5,
) -> str:
    """Keyframe track for the moving crop, expressed relative to the trim."""
    if crop_w >= src_w:
        return ""
    lines: list[str] = []
    t = trim_start
    while t <= trim_end + 1e-6:
        x = _crop_x(analysis, t, src_w, crop_w, focus)
        lines.append(f"{max(0.0, t - trim_start):.3f} crop@rf x {x};")
        t += step
    if not lines:
        lines.append("0.000 crop@rf x 0;")
    return "\n".join(lines) + "\n"


def plan_segments(duration: float, peaks: list[float], zoom: float) -> list[tuple[float, float, float]]:
    """Split the timeline around each punch-in window."""
    if zoom <= 1.001:
        return [(0.0, duration, 1.0)]
    segments: list[tuple[float, float, float]] = []
    cursor = 0.0
    for peak in sorted(peaks):
        if peak - cursor < 0.35 or peak < 0.4 or peak > duration - 0.8:
            continue
        segments.append((cursor, peak, 1.0))
        end = min(duration, peak + 0.5)
        segments.append((peak, end, zoom))
        cursor = end
    if cursor < duration - 0.05:
        segments.append((cursor, duration, 1.0))
    if not segments:
        return [(0.0, duration, 1.0)]
    return [seg for seg in segments if seg[1] - seg[0] > 0.05]


def _run_stage(cmd: list[str], label: str) -> None:
    try:
        run(cmd, timeout=1800)
    except Exception as exc:  # surface which pass failed
        raise RuntimeError(f"{label} failed: {exc}") from exc


def _intermediate_encoder(quality: str) -> list[str]:
    """Mastering codec for the hidden reframe/punch passes."""
    return [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18" if quality == "final" else "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
    ]


def _encoder(quality: str, preset: dict) -> list[str]:
    if quality == "preview":
        return [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "27",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
        ]
    return [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "19",
        "-maxrate",
        preset["video_bitrate"],
        "-bufsize",
        f"{int(preset['video_bitrate'].rstrip('M')) * 2}M",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
    ]


def _stage_reframe(
    source: Path,
    out: Path,
    *,
    info: MediaInfo,
    analysis: dict,
    settings: RenderSettings,
    trim_start: float,
    trim_end: float,
    out_w: int,
    out_h: int,
    work: Path,
    quality: str,
) -> None:
    duration = max(0.2, trim_end - trim_start)
    trim_chain = f"trim=start={trim_start:.4f}:end={trim_end:.4f},setpts=PTS-STARTPTS"
    sendcmd_path: Optional[Path] = None
    facecam = analysis.get("facecam")
    landscape = info.width / max(1, info.height) > 1.05

    inputs: list[str] = ["-i", str(source)]
    audio_input = info.has_audio
    if not audio_input:
        inputs += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]

    if settings.reframe.facecam_split and facecam and landscape:
        panel = _even(settings.reframe.facecam_height * out_h / 1920)
        panel = int(min(panel, out_h * 0.45))
        gameplay_h = _even(out_h - panel)
        game_crop_w, game_crop_h = cover_crop(info.width, info.height, out_w, gameplay_h)
        sendcmd = build_sendcmd(
            analysis,
            src_w=info.width,
            crop_w=game_crop_w,
            trim_start=trim_start,
            trim_end=trim_end,
            focus=settings.reframe.focus,
        )
        sendcmd_path = work / "crop_track.cmd"
        sendcmd_path.write_text(sendcmd or "0.000 crop@rf x 0;\n")

        fc_ar = out_w / panel
        fc_w = float(facecam["w"])
        fc_h = float(facecam["h"])
        if fc_w / fc_h > fc_ar:
            fc_h = fc_w / fc_ar
        else:
            fc_w = fc_h * fc_ar
        fc_cx = facecam["x"] + facecam["w"] / 2
        fc_cy = facecam["y"] + facecam["h"] / 2
        fc_x = _clamp(fc_cx - fc_w / 2, 0, max(0, info.width - fc_w))
        fc_y = _clamp(fc_cy - fc_h / 2, 0, max(0, info.height - fc_h))
        fc_w = min(fc_w, info.width)
        fc_h = min(fc_h, info.height)
        fcw = max(2, _even(fc_w))
        fch = max(2, _even(fc_h))
        fcx, fcy = max(0, _even(fc_x)), max(0, _even(fc_y))
        game_y = max(0, _even((info.height - game_crop_h) / 2))

        graph = (
            f"[0:v]{trim_chain},split=2[g][f];"
            f"[g]sendcmd=f={filter_escape(sendcmd_path)},"
            f"crop@rf={game_crop_w}:{game_crop_h}:0:{game_y},"
            f"scale={out_w}:{gameplay_h}:flags=lanczos,setsar=1[gv];"
            f"[f]crop={fcw}:{fch}:{fcx}:{fcy},"
            f"scale={out_w}:{panel}:flags=lanczos,setsar=1[fv];"
            f"[gv][fv]vstack=inputs=2,format=yuv420p[v]"
        )
    else:
        crop_w, crop_h = cover_crop(info.width, info.height, out_w, out_h)
        crop_y = max(0, _even((info.height - crop_h) / 2))
        if crop_w < info.width:
            sendcmd = build_sendcmd(
                analysis,
                src_w=info.width,
                crop_w=crop_w,
                trim_start=trim_start,
                trim_end=trim_end,
                focus=settings.reframe.focus,
            )
            sendcmd_path = work / "crop_track.cmd"
            sendcmd_path.write_text(sendcmd)
            crop_part = (
                f"sendcmd=f={filter_escape(sendcmd_path)},"
                f"crop@rf={crop_w}:{crop_h}:0:{crop_y}"
            )
        else:
            crop_part = f"crop@rf={crop_w}:{crop_h}:0:{crop_y}"
        graph = (
            f"[0:v]{trim_chain},{crop_part},"
            f"scale={out_w}:{out_h}:flags=lanczos,setsar=1,format=yuv420p[v]"
        )

    if audio_input:
        graph += f";[0:a]atrim=start={trim_start:.4f}:end={trim_end:.4f},asetpts=PTS-STARTPTS[a]"
    else:
        graph += f";[1:a]atrim=start=0:end={duration:.4f},asetpts=PTS-STARTPTS[a]"

    cmd = [
        FFMPEG,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *inputs,
        "-filter_complex",
        graph,
        "-map",
        "[v]",
        "-map",
        "[a]",
        *(_intermediate_encoder(quality)),
        "-t",
        f"{duration:.3f}",
        "-r",
        "30",
        "-fps_mode",
        "cfr",
        str(out),
    ]
    _run_stage(cmd, "Auto-reframe")


def _stage_punch(
    base: Path,
    out: Path,
    *,
    segments: list[tuple[float, float, float]],
    out_w: int,
    out_h: int,
    has_audio: bool,
    motion_blur: bool,
) -> None:
    count = len(segments)
    if count <= 1:
        shutil.copyfile(base, out)
        return
    video_split = "".join(f"[vs{i}]" for i in range(count))
    audio_split = "".join(f"[as{i}]" for i in range(count)) if has_audio else ""
    parts = [f"[0:v]split={count}{video_split}"]
    if has_audio:
        parts.append(f"[0:a]asplit={count}{audio_split}")
    for index, (start, end, zoom) in enumerate(segments):
        steps = [f"trim=start={start:.4f}:end={end:.4f}", "setpts=PTS-STARTPTS"]
        if zoom > 1.001:
            steps.append(f"scale=ceil(iw*{zoom:.4f}/2)*2:ceil(ih*{zoom:.4f}/2)*2:flags=lanczos")
            if motion_blur:
                steps.append("tmix=frames=2")
            steps.append(f"crop={out_w}:{out_h}:(iw-{out_w})/2:(ih-{out_h})/2")
        steps += ["fps=30", "setsar=1", "format=yuv420p"]
        parts.append(f"[vs{index}]" + ",".join(steps) + f"[v{index}]")
        if has_audio:
            parts.append(
                f"[as{index}]atrim=start={start:.4f}:end={end:.4f},asetpts=PTS-STARTPTS[a{index}]"
            )

    concat_inputs: list[str] = []
    for index in range(count):
        concat_inputs.append(f"[v{index}]")
        if has_audio:
            concat_inputs.append(f"[a{index}]")
    joined = "".join(concat_inputs)
    if has_audio:
        parts.append(f"{joined}concat=n={count}:v=1:a=1[v][a]")
    else:
        parts.append(f"{joined}concat=n={count}:v=1:a=0[v]")
    cmd = [
        FFMPEG,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(base),
        "-filter_complex",
        ";".join(parts),
        "-map",
        "[v]",
    ]
    if has_audio:
        cmd += ["-map", "[a]"]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "17",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        str(out),
    ]
    _run_stage(cmd, "Punch-in pass")


def _stage_composite(
    video: Path,
    out: Path,
    *,
    settings: RenderSettings,
    duration: float,
    out_w: int,
    out_h: int,
    overlay_path: Optional[Path],
    music: Optional[Path],
    sfx: Optional[Path],
    flash_times: list[float],
    quality: str,
) -> None:
    preset = PRESETS[settings.preset]
    inputs: list[str] = ["-i", str(video)]
    index = 1
    music_index: Optional[int] = None
    sfx_index: Optional[int] = None
    overlay_index: Optional[int] = None
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        music_index = index
        index += 1
    if sfx:
        inputs += ["-i", str(sfx)]
        sfx_index = index
        index += 1
    if overlay_path:
        inputs += ["-f", "concat", "-safe", "0", "-i", str(overlay_path)]
        overlay_index = index
        index += 1

    video_filters: list[str] = []
    if abs(settings.effects.saturation - 1.0) > 0.01:
        video_filters.append(f"eq=saturation={settings.effects.saturation:.3f}")
    if settings.effects.fade_in:
        video_filters.append("fade=t=in:st=0:d=0.25")
    if settings.effects.flash and flash_times:
        windows = "+".join(
            f"between(t,{max(0.0, t):.3f},{max(0.0, t) + 0.08:.3f})" for t in flash_times[:3]
        )
        video_filters.append(
            f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.65:t=fill:enable='{windows}'"
        )
    video_filters.append("format=yuv420p")

    parts = [f"[0:v]{','.join(video_filters)}[base]"]
    if overlay_index is not None:
        parts.append(f"[{overlay_index}:v]fps=30,format=rgba,setsar=1[ov]")
        parts.append("[base][ov]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]")
    else:
        parts.append("[base]null[v]")

    audio_parts: list[str] = []
    original_volume = settings.audio.original_volume
    if music and settings.audio.duck_music:
        audio_parts.append(
            f"[0:a]volume={original_volume:.3f},"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"asplit=2[main][key]"
        )
    else:
        audio_parts.append(
            f"[0:a]volume={original_volume:.3f},"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[main]"
        )

    mix_inputs = ["[main]"]
    if music is not None and music_index is not None:
        audio_parts.append(
            f"[{music_index}:a]atrim=start=0:end={duration:.3f},asetpts=PTS-STARTPTS,"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"volume={settings.audio.music_volume:.3f}[musraw]"
        )
        if settings.audio.duck_music:
            audio_parts.append(
                "[musraw][key]sidechaincompress=threshold=0.035:ratio=7:attack=15:release=280:"
                "makeup=1[mus]"
            )
        else:
            audio_parts.append("[musraw]anull[mus]")
        mix_inputs.append("[mus]")

    if sfx is not None and sfx_index is not None:
        audio_parts.append(
            f"[{sfx_index}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"volume={settings.effects.sfx_volume:.3f}[sfx]"
        )
        mix_inputs.append("[sfx]")

    if len(mix_inputs) > 1:
        audio_parts.append(
            f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:normalize=0[mix]"
        )
        audio_parts.append("[mix]alimiter=limit=0.95:level=false[a]")
    else:
        audio_parts.append("[main]anull[a]")

    graph = ";".join(parts + audio_parts)
    cmd = [
        FFMPEG,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *inputs,
        "-filter_complex",
        graph,
        "-map",
        "[v]",
        "-map",
        "[a]",
        *(_encoder(quality, preset)),
        "-t",
        f"{duration:.3f}",
        "-r",
        "30",
        "-fps_mode",
        "cfr",
        str(out),
    ]
    _run_stage(cmd, "Captions & audio")


def render_project(
    *,
    project: dict,
    source: Path,
    quality: str,
    out_path: Path,
    work_dir: Path,
    analysis: dict,
    transcript: Optional[Transcript],
    music: Optional[Path],
    progress: Optional[ProgressFn] = None,
) -> dict:
    """Render ``source`` according to the project settings and return metadata."""
    settings = RenderSettings.model_validate(project["settings"])
    info = probe(source)
    duration = info.duration or 0.0
    trim_start = _clamp(settings.trim.start, 0, max(0.0, duration - 0.3))
    trim_end = settings.trim.end if settings.trim.end is not None else duration
    trim_end = _clamp(trim_end, trim_start + 0.2, duration or trim_start + 0.2)
    clip_duration = max(0.2, trim_end - trim_start)
    out_w, out_h = target_size(settings, quality)

    work_dir.mkdir(parents=True, exist_ok=True)
    for stale in work_dir.glob("*.mp4"):
        stale.unlink(missing_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def report(value: float, message: str) -> None:
        if progress:
            progress(value, message)

    report(0.05, "Reframing to vertical")
    base = work_dir / "base.mp4"
    _stage_reframe(
        source,
        base,
        info=info,
        analysis=analysis,
        settings=settings,
        trim_start=trim_start,
        trim_end=trim_end,
        out_w=out_w,
        out_h=out_h,
        work=work_dir,
        quality=quality,
    )

    peaks = analyze_mod.hype_peaks(
        analysis,
        start=trim_start,
        end=trim_end,
        count=settings.effects.punch_in_count if settings.effects.punch_ins else 0,
    )
    relative_peaks = [round(p - trim_start, 3) for p in peaks]
    segments = plan_segments(clip_duration, relative_peaks, settings.effects.punch_in_zoom)

    report(0.4, "Punching in on hype moments")
    punched = work_dir / "punched.mp4"
    if len(segments) > 1:
        _stage_punch(
            base,
            punched,
            segments=segments,
            out_w=out_w,
            out_h=out_h,
            has_audio=True,
            motion_blur=bool(settings.effects.motion_blur),
        )
    else:
        punched = base

    overlay_path = build_overlay_track(
        transcript=transcript,
        settings=settings,
        width=out_w,
        height=out_h,
        duration=clip_duration,
        out_dir=work_dir / "overlay",
        time_offset=trim_start,
        progress=report,
    )

    sfx_path: Optional[Path] = None
    if settings.effects.sfx and relative_peaks and settings.effects.sfx_volume > 0:
        report(0.68, "Placing sound effects")
        sfx_path = build_sfx_track(
            relative_peaks,
            clip_duration,
            work_dir / "sfx.wav",
            volume=settings.effects.sfx_volume,
        )

    flash_times = relative_peaks[:3] if settings.effects.flash else []
    report(0.75, "Compositing captions & audio")
    _stage_composite(
        punched,
        out_path,
        settings=settings,
        duration=clip_duration,
        out_w=out_w,
        out_h=out_h,
        overlay_path=overlay_path,
        music=music,
        sfx=sfx_path,
        flash_times=flash_times,
        quality=quality,
    )
    shutil.rmtree(work_dir / "overlay", ignore_errors=True)

    report(0.95, "Finalising")
    result = probe(out_path)
    return {
        "path": out_path,
        "width": result.width,
        "height": result.height,
        "duration": round(clip_duration, 3),
        "size_bytes": out_path.stat().st_size,
        "quality": quality,
        "preset": settings.preset,
        "punch_ins": max(0, len(segments) - 1),
        "facecam_split": bool(settings.reframe.facecam_split and analysis.get("facecam")),
        "captions": bool(settings.captions.enabled and transcript),
        "overlays": len(settings.overlays),
    }
