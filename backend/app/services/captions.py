"""Caption planning: word grouping and styled runs.

The actual pixels are produced by :mod:`app.services.overlay`, which draws each
run with Pillow so the app does not depend on an FFmpeg build with libass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..schemas import CaptionStyle, Transcript

MAX_LINE_SECONDS = 2.8
PAUSE_BREAK = 0.42


@dataclass
class CaptionRun:
    start: float
    end: float
    words: list[str] = field(default_factory=list)
    starts: list[float] = field(default_factory=list)
    ends: list[float] = field(default_factory=list)
    active: int = 0


def hex_to_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    text = (value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return (255, 255, 255, alpha)
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), alpha)
    except ValueError:
        return (255, 255, 255, alpha)


def _word_fields(word) -> tuple[float, float, str]:
    if isinstance(word, dict):
        return float(word["start"]), float(word["end"]), str(word["word"])
    return float(word.start), float(word.end), str(word.word)


PUNCTUATION = set(".,!?;:…—–-")


def transcript_words(transcript: Optional[Transcript]) -> list[dict]:
    """Flatten Whisper words and repair tokenisation quirks.

    Whisper emits contractions as multiple tokens (``Y`` + ``'ALL``) and can
    produce zero-length words. Reattach leading apostrophes/punctuation to the
    previous word and enforce a minimum duration so captions never flicker.
    """
    if not transcript:
        return []
    words: list[dict] = []
    source = transcript.words or []
    if not source:
        for segment in transcript.segments:
            source.extend(segment.words)
    for word in source:
        start, end, text = _word_fields(word)
        text = text.strip()
        if not text:
            continue
        if words:
            previous = words[-1]
            attaches = text[0] in "'’" or all(char in PUNCTUATION for char in text)
            if attaches:
                previous["word"] += text
                previous["end"] = round(max(previous["end"], end), 3)
                continue
            if start < previous["end"]:
                start = previous["end"]
        end = max(end, start + 0.06)
        words.append({"start": round(start, 3), "end": round(end, 3), "word": text})
    words.sort(key=lambda item: item["start"])
    return words


def group_lines(words: list[dict], style: CaptionStyle) -> list[list[dict]]:
    lines: list[list[dict]] = []
    current: list[dict] = []
    for word in words:
        if current:
            gap = word["start"] - current[-1]["end"]
            span = word["end"] - current[0]["start"]
            if (
                len(current) >= style.words_per_line
                or gap > PAUSE_BREAK
                or span > MAX_LINE_SECONDS
            ):
                lines.append(current)
                current = []
        current.append(word)
    if current:
        lines.append(current)
    return lines


def _display(text: str, style: CaptionStyle) -> str:
    return text.upper() if style.uppercase else text


def caption_runs(transcript: Optional[Transcript], style: CaptionStyle) -> list[CaptionRun]:
    """One run per spoken word, each containing the whole visible line."""
    runs: list[CaptionRun] = []
    for line in group_lines(transcript_words(transcript), style):
        if not line:
            continue
        line_end = line[-1]["end"]
        for index, word in enumerate(line):
            start = max(0.0, word["start"])
            end = line[index + 1]["start"] if index + 1 < len(line) else line_end
            if end <= start:
                end = start + 0.12
            runs.append(
                CaptionRun(
                    start=start,
                    end=end,
                    words=[_display(w["word"], style) for w in line],
                    starts=[w["start"] for w in line],
                    ends=[w["end"] for w in line],
                    active=index,
                )
            )
    return runs


def caption_events(transcript: Optional[Transcript], style: CaptionStyle) -> list[dict]:
    """Plain data for the editor transcript panel."""
    result = []
    for line in group_lines(transcript_words(transcript), style):
        result.append(
            {
                "start": round(line[0]["start"], 3),
                "end": round(line[-1]["end"], 3),
                "text": " ".join(_display(w["word"], style) for w in line),
                "words": [
                    {"word": w["word"], "start": round(w["start"], 3), "end": round(w["end"], 3)}
                    for w in line
                ],
            }
        )
    return result
