export type PresetId = "tiktok" | "shorts" | "reels";

export interface CaptionStyle {
  enabled: boolean;
  font: string;
  font_size: number;
  text_color: string;
  active_color: string;
  outline_color: string;
  outline_width: number;
  uppercase: boolean;
  words_per_line: number;
  position_y: number;
  pop_in: boolean;
  background: boolean;
  background_color: string;
}

export interface ReframeSettings {
  facecam_split: boolean;
  focus: "action" | "face" | "center";
  smoothing: number;
  facecam_height: number;
}

export interface EffectSettings {
  punch_ins: boolean;
  punch_in_zoom: number;
  punch_in_count: number;
  sfx: boolean;
  sfx_volume: number;
  motion_blur: boolean;
  flash: boolean;
  saturation: number;
  fade_in: boolean;
}

export interface AudioSettings {
  original_volume: number;
  music_volume: number;
  duck_music: boolean;
}

export interface Trim {
  start: number;
  end: number | null;
}

export interface Overlay {
  id: string;
  kind: "text" | "emoji";
  text: string;
  start: number;
  end: number;
  x: number;
  y: number;
  size: number;
  color: string;
}

export interface RenderSettings {
  preset: PresetId;
  captions: CaptionStyle;
  reframe: ReframeSettings;
  effects: EffectSettings;
  audio: AudioSettings;
  trim: Trim;
  overlays: Overlay[];
}

export interface RenderInfo {
  file: string;
  thumbnail: string | null;
  width: number;
  height: number;
  duration: number;
  size_bytes: number;
  preset: PresetId;
  punch_ins: number;
  facecam_split: boolean;
  captions: boolean;
  settings_hash: string;
  updated_at: string;
}

export interface FacecamBox {
  x: number;
  y: number;
  w: number;
  h: number;
  coverage: number;
  area_ratio: number;
}

export interface AnalysisSummary {
  facecam_detected: boolean;
  facecam: FacecamBox | null;
  peaks: number[];
  peak_count: number;
  tracking_points: number;
  has_audio: boolean;
  duration: number;
  waveform?: number[];
}

export interface CaptionLine {
  start: number;
  end: number;
  text: string;
  words: { word: string; start: number; end: number }[];
}

export interface TranscriptSummary {
  language: string | null;
  language_probability: number | null;
  text: string | null;
  word_count: number;
  segment_count: number;
  preview_words: { word: string; start: number; end: number }[];
}

export interface Job {
  id: string;
  project_id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  message: string;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectUrls {
  source: string | null;
  thumbnail: string | null;
  preview: string | null;
  preview_thumbnail: string | null;
  final: string | null;
  final_thumbnail: string | null;
  music: string | null;
}

export interface ShareInfo {
  slug: string;
  quality: "preview" | "final";
  path: string;
  created_at: string;
}

export interface PublicShare {
  slug: string;
  title: string;
  quality: "preview" | "final";
  duration: number;
  width: number | null;
  height: number | null;
  preset: string | null;
  captions: boolean;
  source_kind: "twitch" | "upload";
  published_at: string | null;
  video_url: string;
  thumbnail_url: string | null;
  download_url: string;
}

export interface Project {
  id: string;
  name: string;
  source_kind: "twitch" | "upload";
  source_url: string | null;
  status: string;
  error: string | null;
  duration: number;
  width: number;
  height: number;
  created_at: string;
  updated_at: string;
  settings: RenderSettings;
  renders: Partial<Record<"preview" | "final", RenderInfo>>;
  has_transcript: boolean;
  has_music: boolean;
  analysis_summary: AnalysisSummary | null;
  active_job: Job | null;
  urls: ProjectUrls;
  share?: ShareInfo | null;
  stale: { preview: boolean; final: boolean };
  caption_lines?: CaptionLine[];
  transcript?: TranscriptSummary | null;
}

export interface Health {
  status: "ok" | "degraded";
  capabilities: {
    ffmpeg: boolean;
    ffprobe: boolean;
    ytdlp: boolean;
    whisper: boolean;
    opencv: boolean;
  };
  whisper_model: string;
  limits: { max_upload_bytes: number; max_clip_seconds: number };
  presets: { id: PresetId; label: string; width: number; height: number; fps: number; video_bitrate: string; description: string }[];
  fonts: string[];
}

export interface Sticker {
  id: string;
  url: string;
}
