"""Request / response models shared by the API and the render pipeline."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CaptionStyle(BaseModel):
    enabled: bool = True
    font: str = "Arial Black"
    font_size: int = Field(92, ge=32, le=220, description="Font size in 1080x1920 design units")
    text_color: str = "#FFFFFF"
    active_color: str = "#FFE600"
    outline_color: str = "#000000"
    outline_width: float = Field(5, ge=0, le=16)
    uppercase: bool = True
    words_per_line: int = Field(4, ge=1, le=9)
    position_y: float = Field(0.74, ge=0.05, le=0.95)
    pop_in: bool = True
    background: bool = False
    background_color: str = "#000000"


class ReframeSettings(BaseModel):
    facecam_split: bool = False
    focus: Literal["action", "face", "center"] = "action"
    smoothing: float = Field(0.45, ge=0, le=0.95)
    facecam_height: int = Field(560, ge=320, le=960, description="Facecam panel height in 1920 units")


class EffectSettings(BaseModel):
    punch_ins: bool = True
    punch_in_zoom: float = Field(1.16, ge=1.0, le=1.6)
    punch_in_count: int = Field(4, ge=0, le=10)
    sfx: bool = True
    sfx_volume: float = Field(0.6, ge=0, le=1.5)
    motion_blur: bool = False
    flash: bool = False
    saturation: float = Field(1.06, ge=0.5, le=1.6)
    fade_in: bool = False


class AudioSettings(BaseModel):
    original_volume: float = Field(1.0, ge=0, le=2.0)
    music_volume: float = Field(0.22, ge=0, le=1.5)
    duck_music: bool = True


class Trim(BaseModel):
    start: float = Field(0.0, ge=0)
    end: Optional[float] = Field(None, ge=0)


class Overlay(BaseModel):
    id: str
    kind: Literal["text", "emoji"] = "text"
    text: str
    start: float = 0.0
    end: float = 3.0
    x: float = Field(0.5, ge=0, le=1)
    y: float = Field(0.28, ge=0, le=1)
    size: int = Field(84, ge=20, le=220)
    color: str = "#FFFFFF"


class RenderSettings(BaseModel):
    preset: Literal["tiktok", "shorts", "reels"] = "tiktok"
    captions: CaptionStyle = CaptionStyle()
    reframe: ReframeSettings = ReframeSettings()
    effects: EffectSettings = EffectSettings()
    audio: AudioSettings = AudioSettings()
    trim: Trim = Trim()
    overlays: list[Overlay] = Field(default_factory=list)


class ProjectSettingsUpdate(BaseModel):
    name: Optional[str] = None
    settings: Optional[RenderSettings] = None


class ImportRequest(BaseModel):
    url: str = Field(min_length=5, max_length=2048)


class RenderRequest(BaseModel):
    quality: Literal["preview", "final"] = "preview"


class ShareRequest(BaseModel):
    quality: Literal["auto", "preview", "final"] = "auto"


class Word(BaseModel):
    start: float
    end: float
    word: str


class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    words: list[Word] = Field(default_factory=list)


class Transcript(BaseModel):
    language: str
    language_probability: float = 0.0
    text: str
    words: list[Word] = Field(default_factory=list)
    segments: list[TranscriptSegment] = Field(default_factory=list)
    duration: float = 0.0


class Job(BaseModel):
    id: str
    project_id: str
    kind: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None
    created_at: str
    updated_at: str
