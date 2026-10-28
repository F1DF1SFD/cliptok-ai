"""Whisper speech-to-text with word-level timestamps."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

from ..config import DATA_DIR, WHISPER_COMPUTE, WHISPER_DEVICE, WHISPER_MODEL
from ..schemas import Transcript, TranscriptSegment, Word

ProgressFn = Callable[[float, str], None]
_MODEL_LOCK = threading.Lock()
_MODELS: dict[str, object] = {}


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:
        return False


def _load_model(name: str):
    from faster_whisper import WhisperModel

    key = f"{name}:{WHISPER_DEVICE}:{WHISPER_COMPUTE}"
    with _MODEL_LOCK:
        if key in _MODELS:
            return _MODELS[key]
        models_dir = DATA_DIR / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        device = WHISPER_DEVICE
        if device == "auto":
            device = "cpu"
            try:
                import ctranslate2

                if ctranslate2.get_cuda_device_count() > 0:
                    device = "cuda"
            except Exception:
                device = "cpu"
        model = WhisperModel(
            name,
            device=device,
            compute_type=WHISPER_COMPUTE if device == "cuda" else "int8",
            download_root=str(models_dir),
        )
        _MODELS[key] = model
        return model


def transcribe(
    audio_path: Path,
    *,
    model_name: Optional[str] = None,
    progress: Optional[ProgressFn] = None,
) -> Transcript:
    def report(value: float, message: str) -> None:
        if progress:
            progress(max(0.0, min(1.0, value)), message)

    if not whisper_available():
        raise RuntimeError(
            "Whisper is not installed. Run: backend/.venv/bin/pip install faster-whisper"
        )

    name = model_name or WHISPER_MODEL
    report(0.05, f"Loading Whisper ({name}) - first run downloads the model")
    model = _load_model(name)

    report(0.15, "Transcribing audio")
    segments_iter, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 350},
        condition_on_previous_text=False,
    )
    duration = float(getattr(info, "duration", 0) or 0)
    language = str(getattr(info, "language", "") or "en")
    probability = float(getattr(info, "language_probability", 0) or 0)

    segments: list[TranscriptSegment] = []
    all_words: list[Word] = []
    texts: list[str] = []
    for index, segment in enumerate(segments_iter):
        words: list[Word] = []
        for word in getattr(segment, "words", None) or []:
            text = str(word.word).strip()
            if not text:
                continue
            payload = Word(
                start=round(float(word.start), 3),
                end=round(float(word.end), 3),
                word=text,
            )
            words.append(payload)
            all_words.append(payload)
        segment_text = str(segment.text).strip()
        if words or segment_text:
            segments.append(
                TranscriptSegment(
                    id=index,
                    start=round(float(segment.start), 3),
                    end=round(float(segment.end), 3),
                    text=segment_text,
                    words=words,
                )
            )
            texts.append(segment_text)
        if duration > 0:
            report(0.15 + 0.8 * min(1.0, float(segment.end) / duration), "Transcribing audio")

    report(0.98, "Building word timings")
    return Transcript(
        language=language,
        language_probability=round(probability, 3),
        text=" ".join(t for t in texts if t).strip(),
        words=all_words,
        segments=segments,
        duration=round(duration, 3),
    )
