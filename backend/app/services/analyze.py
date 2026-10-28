"""Audio + visual analysis used by auto-reframing and punch-in placement.

OpenCV is used to (a) locate faces, (b) distinguish a corner facecam from the
gameplay, and (c) fall back to motion-centroid tracking when no face is
visible. Audio loudness peaks drive the automatic punch-ins and sound effects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .media import MediaError, decode_audio_mono, probe

ProgressFn = Callable[[float, str], None]

SAMPLE_SECONDS = 0.25
DETECT_WIDTH = 480


def opencv_available() -> bool:
    try:
        import cv2  # noqa: F401

        return True
    except Exception:
        return False


def _cascade():
    import cv2

    path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    if not path.exists():
        return None
    cascade = cv2.CascadeClassifier(str(path))
    return None if cascade.empty() else cascade


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    return inter / (aw * ah + bw * bh - inter)


def _detect_facecam(samples: list[dict], progress_cb: Optional[ProgressFn] = None) -> Optional[dict]:
    """Identify a stable face region that behaves like a streamer facecam."""
    if len(samples) < 8:
        return None
    clusters: list[dict] = []
    for sample in samples:
        for face in sample["faces"]:
            cx, cy = face[0] + face[2] / 2, face[1] + face[3] / 2
            best, best_iou = None, 0.0
            for cluster in clusters:
                iou = _iou(face, cluster["rect"])
                if iou > best_iou:
                    best, best_iou = cluster, iou
            if best is not None and best_iou > 0.35:
                best["count"] += 1
                best["rects"].append(face)
                best["rect"] = tuple(
                    float(np.median([r[i] for r in best["rects"]])) for i in range(4)
                )
            else:
                clusters.append({"count": 1, "rect": face, "rects": [face], "cx": cx, "cy": cy})

    best_cluster = max(clusters, key=lambda c: c["count"], default=None)
    if not best_cluster:
        return None
    coverage = best_cluster["count"] / len(samples)
    if coverage < 0.5:
        return None
    areas = [
        (r[2] * r[3]) / (sample_w * sample_h)
        for r, sample_w, sample_h in [
            (r, samples[0]["width"], samples[0]["height"]) for r in best_cluster["rects"]
        ]
    ]
    area_ratio = float(np.median(areas))
    # Streamer facecams are small (a few percent of a 720p/1080p frame).
    if not (0.002 <= area_ratio <= 0.25):
        return None

    x, y, w, h = best_cluster["rect"]
    pad_x, pad_y = w * 0.35, h * 0.45
    x = max(0.0, x - pad_x)
    y = max(0.0, y - pad_y)
    w = min(samples[0]["width"] - x, w + pad_x * 2)
    h = min(samples[0]["height"] - y, h + pad_y * 2)
    return {
        "x": round(x, 1),
        "y": round(y, 1),
        "w": round(w, 1),
        "h": round(h, 1),
        "coverage": round(coverage, 3),
        "area_ratio": round(area_ratio, 4),
    }


def _audio_energy(video: Path, duration: float) -> tuple[list[list[float]], list[float]]:
    try:
        raw = decode_audio_mono(video, sample_rate=8000)
    except MediaError:
        return [], []
    if not raw:
        return [], []
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    window = int(8000 * 0.2)
    if len(samples) < window * 2:
        return [], []
    usable = len(samples) // window * window
    frames = samples[:usable].reshape(-1, window)
    rms = np.sqrt(np.mean(frames**2, axis=1))
    smooth = np.convolve(rms, np.ones(3) / 3, mode="same")
    peak = float(np.percentile(smooth, 95)) or float(smooth.max()) or 1.0
    normalized = np.clip(smooth / peak, 0, 1)
    energy = [[round(i * 0.2, 2), round(float(v), 4)] for i, v in enumerate(normalized)]

    # Peak picking with non-maximum suppression.
    threshold = max(0.45, float(np.mean(normalized) + 0.55 * np.std(normalized)))
    peaks: list[float] = []
    for i in range(1, len(normalized) - 1):
        if normalized[i] < threshold:
            continue
        if normalized[i] < normalized[i - 1] or normalized[i] < normalized[i + 1]:
            continue
        t = i * 0.2
        if peaks and t - peaks[-1] < 1.5:
            if normalized[i] > normalized[int(peaks[-1] / 0.2)]:
                peaks[-1] = round(t, 2)
            continue
        peaks.append(round(t, 2))
    return energy, peaks


def analyze_video(
    video: Path,
    *,
    progress: Optional[ProgressFn] = None,
    focus: str = "action",
    smoothing: float = 0.45,
) -> dict:
    """Return a compact analysis document for ``video``."""
    import cv2

    if not opencv_available():
        raise RuntimeError("OpenCV is not installed in the backend environment")

    def report(value: float, message: str) -> None:
        if progress:
            progress(max(0.0, min(1.0, value)), message)

    info = probe(video)
    report(0.05, "Reading frames")

    cascade = _cascade()
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError("Could not open the video for analysis")

    fps = cap.get(cv2.CAP_PROP_FPS) or info.fps or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = info.duration or (total_frames / fps if fps else 0)
    step = max(1, int(round(fps * SAMPLE_SECONDS)))

    samples: list[dict] = []
    prev_small: Optional[np.ndarray] = None
    frame_index = 0
    max_samples = 2400

    while len(samples) < max_samples:
        if not cap.grab():
            break
        if frame_index % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            height, width = frame.shape[:2]
            scale = DETECT_WIDTH / float(width) if width > DETECT_WIDTH else 1.0
            small = cv2.resize(frame, (int(width * scale), int(height * scale)))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)

            faces: list[tuple[float, float, float, float]] = []
            if cascade is not None:
                found = cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.12,
                    minNeighbors=5,
                    minSize=(int(gray.shape[1] * 0.05), int(gray.shape[1] * 0.05)),
                )
                for (fx, fy, fw, fh) in found:
                    faces.append(
                        (
                            round(fx / scale, 1),
                            round(fy / scale, 1),
                            round(fw / scale, 1),
                            round(fh / scale, 1),
                        )
                    )

            motion = [0.5, 0.5]
            motion_strength = 0.0
            if prev_small is not None and prev_small.shape == gray.shape:
                diff = cv2.absdiff(gray, prev_small)
                _, mask = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
                ys, xs = np.nonzero(mask)
                if len(xs) > 40:
                    motion = [float(xs.mean()) / gray.shape[1], float(ys.mean()) / gray.shape[0]]
                    motion_strength = float(len(xs)) / mask.size
            prev_small = gray

            samples.append(
                {
                    "t": round(frame_index / fps, 2),
                    "faces": faces,
                    "motion": motion,
                    "motion_strength": round(motion_strength, 4),
                    "width": width,
                    "height": height,
                }
            )
            if len(samples) % 40 == 0:
                report(0.05 + 0.45 * min(1.0, len(samples) / max(1, duration / SAMPLE_SECONDS)),
                       f"Scanning frames ({len(samples)})")
        frame_index += 1
    cap.release()

    if not samples:
        raise RuntimeError("No frames could be decoded from this video")

    report(0.55, "Detecting facecam")
    facecam = _detect_facecam(samples)

    def inside_facecam(face) -> bool:
        if not facecam:
            return False
        fx, fy, fw, fh = face
        cx, cy = fx + fw / 2, fy + fh / 2
        return (
            facecam["x"] <= cx <= facecam["x"] + facecam["w"]
            and facecam["y"] <= cy <= facecam["y"] + facecam["h"]
        )

    report(0.62, "Tracking the action")
    raw: list[tuple[float, float]] = []
    for sample in samples:
        w = sample["width"] or info.width
        h = sample["height"] or info.height
        target: Optional[float] = None
        if focus == "center":
            target = 0.5
        else:
            candidates = [
                f for f in sample["faces"] if not inside_facecam(f) and (f[2] * f[3]) / (w * h) > 0.02
            ]
            face_center = None
            if candidates:
                biggest = max(candidates, key=lambda f: f[2] * f[3])
                face_center = (biggest[0] + biggest[2] / 2) / w
            motion_cx = sample["motion"][0]
            if focus == "face":
                target = face_center if face_center is not None else motion_cx
            else:
                if face_center is not None and sample["motion_strength"] > 0.002:
                    target = 0.7 * face_center + 0.3 * motion_cx
                elif face_center is not None:
                    target = face_center
                else:
                    target = motion_cx
        if target is None:
            target = raw[-1][1] if raw else 0.5
        if abs(target - 0.5) < 0.06:
            target = 0.5
        target = min(0.9, max(0.1, target))
        raw.append((sample["t"], target))

    alpha = max(0.04, 1.0 - smoothing)
    smoothed: list[tuple[float, float]] = []
    previous = raw[0][1]
    max_step = 0.08
    for t, value in raw:
        previous = previous + alpha * (value - previous)
        previous = min(previous + max_step, max(previous - max_step, previous))
        smoothed.append((t, round(previous, 4)))

    # Keep a 2 Hz keyframe track; the renderer interpolates with sendcmd.
    trajectory = [list(p) for p in smoothed[:: max(1, int(round(0.5 / SAMPLE_SECONDS)))]]
    if trajectory and trajectory[-1][0] < duration:
        trajectory.append([round(duration, 2), smoothed[-1][1]])

    report(0.82, "Finding hype moments")
    energy, peaks = _audio_energy(video, duration)

    report(0.95, "Finishing analysis")
    return {
        "width": info.width,
        "height": info.height,
        "duration": round(info.duration, 3),
        "fps": info.fps,
        "has_audio": info.has_audio,
        "facecam": facecam,
        "trajectory": trajectory,
        "energy": energy,
        "peaks": peaks,
        "focus": focus,
        "smoothed": smoothing,
        "sampled_frames": len(samples),
        "face_samples": sum(1 for s in samples if s["faces"]),
    }


def principal_center(analysis: dict, t: float) -> float:
    """Interpolate the tracked center (0..1) at time ``t``."""
    traj = analysis.get("trajectory") or []
    if not traj:
        return 0.5
    for i, (ts, cx) in enumerate(traj):
        if ts >= t:
            if i == 0:
                return float(cx)
            t0, c0 = traj[i - 1]
            span = max(1e-6, ts - t0)
            ratio = (t - t0) / span
            return float(c0 + (cx - c0) * ratio)
    return float(traj[-1][1])


def hype_peaks(analysis: dict, *, start: float, end: float, count: int) -> list[float]:
    peaks = [p for p in analysis.get("peaks", []) if start + 0.3 <= p <= end - 0.6]
    peaks.sort()
    if count <= 0:
        return []
    # Keep the loudest peaks while enforcing spacing.
    energy = analysis.get("energy") or []
    def level(t: float) -> float:
        if not energy:
            return 0.0
        idx = min(len(energy) - 1, max(0, int(round(t / 0.2))))
        return energy[idx][1]

    ranked = sorted(peaks, key=level, reverse=True)
    chosen: list[float] = []
    for p in ranked:
        if all(abs(p - c) >= 1.6 for c in chosen):
            chosen.append(p)
        if len(chosen) >= count:
            break
    return sorted(chosen)


def overview(analysis: dict) -> dict:
    """Small summary embedded in the project payload for the UI."""
    peaks = analysis.get("peaks") or []
    facecam = analysis.get("facecam")

    waveform: list[float] = []
    energy = analysis.get("energy") or []
    if energy:
        buckets = 96
        size = max(1, len(energy) // buckets)
        for index in range(buckets):
            chunk = [point[1] for point in energy[index * size : (index + 1) * size]]
            if chunk:
                waveform.append(round(max(chunk), 3))

    return {
        "facecam_detected": bool(facecam),
        "facecam": facecam,
        "peaks": peaks[:12],
        "peak_count": len(peaks),
        "tracking_points": len(analysis.get("trajectory") or []),
        "has_audio": bool(analysis.get("has_audio")),
        "duration": analysis.get("duration"),
        "waveform": waveform,
    }
