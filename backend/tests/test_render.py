from pathlib import Path

from app.schemas import RenderSettings
from app.services.render import (
    build_sendcmd,
    cover_crop,
    filter_escape,
    plan_segments,
    target_size,
)


def test_cover_crop_matches_nine_by_sixteen():
    width, height = cover_crop(1280, 720, 1080, 1920)
    assert width == 404
    assert height == 720
    assert abs(width / height - 9 / 16) < 0.01


def test_cover_crop_handles_portrait_source():
    width, height = cover_crop(720, 1280, 1080, 1920)
    assert (width, height) == (720, 1280)


def test_target_size_preview_is_half_resolution():
    settings = RenderSettings()
    assert target_size(settings, "final") == (1080, 1920)
    assert target_size(settings, "preview") == (540, 960)


def test_plan_segments_keeps_total_duration():
    segments = plan_segments(12.0, [2.0, 6.0], 1.2)
    assert len(segments) == 5
    assert segments[0][0] == 0.0
    assert segments[-1][1] == 12.0
    assert abs(sum(end - start for start, end, _ in segments) - 12.0) < 1e-6
    assert any(zoom > 1 for _, _, zoom in segments)


def test_plan_segments_without_zoom_is_single_segment():
    assert plan_segments(8.0, [2.0, 5.0], 1.0) == [(0.0, 8.0, 1.0)]


def test_sendcmd_clamps_the_crop_to_the_frame():
    analysis = {"trajectory": [[0.0, 0.0], [1.0, 0.0], [2.0, 1.0]]}
    commands = build_sendcmd(
        analysis, src_w=1280, crop_w=404, trim_start=1.0, trim_end=2.0, focus="action", step=0.5
    )
    lines = [line for line in commands.strip().splitlines() if line]
    assert len(lines) == 3
    values = [int(line.rsplit(" ", 1)[1].rstrip(";")) for line in lines]
    assert all(0 <= value <= 1280 - 404 for value in values)
    assert values[0] == 0
    assert values[-1] == 1280 - 404
    assert lines[0].startswith("0.000 ")


def test_center_focus_ignores_trajectory():
    analysis = {"trajectory": [[0.0, 0.05], [1.0, 0.95]]}
    commands = build_sendcmd(
        analysis, src_w=1000, crop_w=400, trim_start=0, trim_end=1, focus="center", step=0.5
    )
    values = [int(line.rsplit(" ", 1)[1].rstrip(";")) for line in commands.strip().splitlines()]
    assert set(values) == {300}


def test_filter_escape_escapes_special_characters():
    escaped = filter_escape(__import__("pathlib").Path("/tmp/a:b,c d/ass.ass"))
    assert "\\:" in escaped and "\\," in escaped and "\\ " in escaped


def test_filter_escape_handles_windows_paths():
    # FFmpeg filtergraphs need forward slashes and escaped drive colons, which is
    # what keeps the packaged Windows app able to read its sendcmd scripts.
    escaped = filter_escape(Path(r"C:\Users\Nova\App Data\Local\ClipTokAI\work\crop.cmd"))
    assert escaped.startswith("C\\:/Users/Nova/App\\ Data/Local/ClipTokAI/work/crop.cmd")
    assert "\\" not in escaped.replace("\\:", "").replace("\\ ", "")
