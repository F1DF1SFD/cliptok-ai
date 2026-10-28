"use client";

import * as React from "react";
import {
  Captions,
  Crop,
  Download,
  Film,
  Flame,
  ImagePlus,
  Loader2,
  Music2,
  Plus,
  Sparkles,
  Trash2,
  Upload,
  Wand2,
  Zap,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { mediaUrl } from "@/lib/api";
import { SharePanel } from "@/components/editor/share-panel";
import type {
  AudioSettings,
  CaptionStyle,
  EffectSettings,
  Job,
  Overlay,
  Project,
  ReframeSettings,
  RenderSettings,
  Sticker,
} from "@/lib/types";
import { clamp, cn, formatBytes, formatDuration, timecode } from "@/lib/utils";

interface Props {
  project: Project;
  settings: RenderSettings;
  fonts: string[];
  stickers: Sticker[];
  duration: number;
  currentTime: number;
  job: Job | null;
  rendering: boolean;
  musicBusy: boolean;
  onSettingsChange: (patch: Partial<RenderSettings>) => void;
  onRenderPreview: () => void;
  onRenderFinal: () => void;
  onAnalyze: () => void;
  onTranscribe: () => void;
  onMusicUpload: (file: File) => void;
  onMusicRemove: () => void;
  onSeek: (time: number) => void;
}

export function SettingsPanel({
  project,
  settings,
  fonts,
  stickers,
  duration,
  currentTime,
  job,
  rendering,
  musicBusy,
  onSettingsChange,
  onRenderPreview,
  onRenderFinal,
  onAnalyze,
  onTranscribe,
  onMusicUpload,
  onMusicRemove,
  onSeek,
}: Props) {
  const [selectedOverlay, setSelectedOverlay] = React.useState<string | null>(null);
  const busy = Boolean(job && (job.status === "running" || job.status === "queued"));

  const patchCaptions = (patch: Partial<CaptionStyle>) =>
    onSettingsChange({ captions: { ...settings.captions, ...patch } });
  const patchReframe = (patch: Partial<ReframeSettings>) =>
    onSettingsChange({ reframe: { ...settings.reframe, ...patch } });
  const patchEffects = (patch: Partial<EffectSettings>) =>
    onSettingsChange({ effects: { ...settings.effects, ...patch } });
  const patchAudio = (patch: Partial<AudioSettings>) =>
    onSettingsChange({ audio: { ...settings.audio, ...patch } });

  const addOverlay = (kind: "text" | "emoji", sticker?: Sticker) => {
    const start = Math.min(Math.max(0, currentTime), Math.max(0, duration - 1.5));
    const overlay: Overlay = {
      id: Math.random().toString(36).slice(2, 10),
      kind,
      text: kind === "emoji" ? sticker?.id ?? stickers[0]?.id ?? "fire" : "NO WAY",
      start: Math.round(start * 10) / 10,
      end: Math.min(duration || start + 3, Math.round((start + 2.5) * 10) / 10),
      x: 0.5,
      y: kind === "emoji" ? 0.32 : 0.22,
      size: kind === "emoji" ? 120 : 90,
      color: "#FFFFFF",
    };
    onSettingsChange({ overlays: [...settings.overlays, overlay] });
    setSelectedOverlay(overlay.id);
  };

  const updateOverlay = (id: string, patch: Partial<Overlay>) =>
    onSettingsChange({
      overlays: settings.overlays.map((overlay) =>
        overlay.id === id ? { ...overlay, ...patch } : overlay,
      ),
    });

  const removeOverlay = (id: string) => {
    onSettingsChange({ overlays: settings.overlays.filter((overlay) => overlay.id !== id) });
    if (selectedOverlay === id) setSelectedOverlay(null);
  };

  const activeOverlay = settings.overlays.find((overlay) => overlay.id === selectedOverlay) ?? null;
  const peaks = project.analysis_summary?.peaks ?? [];
  const facecam = project.analysis_summary?.facecam;

  return (
    <div className="panel flex h-full flex-col overflow-hidden">
      <Tabs defaultValue="captions" className="flex h-full min-h-0 flex-col">
        <div className="border-b border-white/[0.06] p-3">
          <TabsList className="grid h-auto w-full grid-cols-3 gap-1 bg-black/20 p-1">
            <TabsTrigger value="captions" className="flex-col gap-0.5 py-1.5 text-[10px]">
              <Captions className="size-3.5" /> Captions
            </TabsTrigger>
            <TabsTrigger value="reframe" className="flex-col gap-0.5 py-1.5 text-[10px]">
              <Crop className="size-3.5" /> Reframe
            </TabsTrigger>
            <TabsTrigger value="effects" className="flex-col gap-0.5 py-1.5 text-[10px]">
              <Flame className="size-3.5" /> Effects
            </TabsTrigger>
            <TabsTrigger value="audio" className="flex-col gap-0.5 py-1.5 text-[10px]">
              <Music2 className="size-3.5" /> Audio
            </TabsTrigger>
            <TabsTrigger value="overlays" className="flex-col gap-0.5 py-1.5 text-[10px]">
              <ImagePlus className="size-3.5" /> Overlays
            </TabsTrigger>
            <TabsTrigger value="export" className="flex-col gap-0.5 py-1.5 text-[10px]">
              <Download className="size-3.5" /> Export
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4 scrollbar-thin">
          {/* ------------------------------- Captions ------------------------------- */}
          <TabsContent value="captions" className="mt-0 space-y-5">
            <ToggleRow
              label="Burned-in captions"
              description="Word-by-word styling rendered into the MP4."
              checked={settings.captions.enabled}
              onChange={(checked) => patchCaptions({ enabled: checked })}
            />

            <CaptionPreview style={settings.captions} />

            {!project.has_transcript ? (
              <div className="rounded-xl border border-primary/25 bg-primary/[0.07] p-3">
                <p className="text-xs font-semibold">No transcript yet</p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                  Run Whisper once and you get word-level timing for every caption style change.
                </p>
                <Button
                  className="mt-2.5 w-full"
                  size="sm"
                  onClick={onTranscribe}
                  disabled={busy}
                >
                  {job?.kind === "transcribe" && busy ? (
                    <>
                      <Loader2 className="animate-spin" /> Transcribing… {Math.round(job.progress * 100)}%
                    </>
                  ) : (
                    <>
                      <Captions /> Transcribe with Whisper
                    </>
                  )}
                </Button>
              </div>
            ) : (
              <div className="flex items-center justify-between rounded-xl border border-emerald-400/20 bg-emerald-400/[0.05] px-3 py-2 text-[11px] text-emerald-200/80">
                <span className="inline-flex items-center gap-1.5">
                  <Captions className="size-3.5" />
                  {project.transcript?.word_count ?? 0} words ·{" "}
                  {project.transcript?.language?.toUpperCase() ?? "EN"}
                </span>
                <button
                  type="button"
                  onClick={onTranscribe}
                  disabled={busy}
                  className="text-twitch-light underline-offset-2 hover:underline disabled:opacity-50"
                >
                  Re-run
                </button>
              </div>
            )}

            <div className="space-y-1.5">
              <Label>Font</Label>
              <Select
                value={settings.captions.font}
                onChange={(event) => patchCaptions({ font: event.target.value })}
              >
                {(fonts.length ? fonts : ["Arial Black"]).map((font) => (
                  <option key={font} value={font} className="bg-[#150d22]">
                    {font}
                  </option>
                ))}
              </Select>
            </div>

            <SliderRow
              label="Font size"
              value={settings.captions.font_size}
              min={40}
              max={170}
              step={2}
              suffix="px"
              onChange={(value) => patchCaptions({ font_size: value })}
            />
            <SliderRow
              label="Words per line"
              value={settings.captions.words_per_line}
              min={1}
              max={7}
              step={1}
              onChange={(value) => patchCaptions({ words_per_line: value })}
            />
            <SliderRow
              label="Vertical position"
              value={Math.round(settings.captions.position_y * 100)}
              min={15}
              max={92}
              step={1}
              suffix="%"
              onChange={(value) => patchCaptions({ position_y: value / 100 })}
            />
            <SliderRow
              label="Outline"
              value={settings.captions.outline_width}
              min={0}
              max={12}
              step={0.5}
              suffix="px"
              onChange={(value) => patchCaptions({ outline_width: value })}
            />

            <div className="grid grid-cols-3 gap-2">
              <ColorField
                label="Text"
                value={settings.captions.text_color}
                onChange={(value) => patchCaptions({ text_color: value })}
              />
              <ColorField
                label="Active"
                value={settings.captions.active_color}
                onChange={(value) => patchCaptions({ active_color: value })}
              />
              <ColorField
                label="Outline"
                value={settings.captions.outline_color}
                onChange={(value) => patchCaptions({ outline_color: value })}
              />
            </div>

            <div className="space-y-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
              <ToggleRow
                label="Uppercase"
                checked={settings.captions.uppercase}
                onChange={(checked) => patchCaptions({ uppercase: checked })}
                compact
              />
              <ToggleRow
                label="Pop-in animation"
                checked={settings.captions.pop_in}
                onChange={(checked) => patchCaptions({ pop_in: checked })}
                compact
              />
              <ToggleRow
                label="Text box"
                checked={settings.captions.background}
                onChange={(checked) => patchCaptions({ background: checked })}
                compact
              />
            </div>
          </TabsContent>

          {/* -------------------------------- Reframe -------------------------------- */}
          <TabsContent value="reframe" className="mt-0 space-y-5">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold">Auto reframe</p>
                <Badge variant={project.analysis_summary ? "success" : "secondary"}>
                  {project.analysis_summary
                    ? `${project.analysis_summary.tracking_points} keyframes`
                    : "not analyzed"}
                </Badge>
              </div>
              <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
                OpenCV tracks faces and motion, then FFmpeg pans a 9:16 crop to follow the action.
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-2.5 w-full"
                onClick={onAnalyze}
                disabled={busy}
              >
                {job?.kind === "analyze" && busy ? (
                  <>
                    <Loader2 className="animate-spin" /> Analyzing… {Math.round(job.progress * 100)}%
                  </>
                ) : (
                  <>
                    <Wand2 /> Re-analyze clip
                  </>
                )}
              </Button>
            </div>

            <ToggleRow
              label="Facecam split layout"
              description={
                facecam
                  ? `Facecam found (${Math.round((facecam.coverage ?? 0) * 100)}% of frames) — stack gameplay above the cam.`
                  : "No stable facecam detected in this clip."
              }
              checked={settings.reframe.facecam_split}
              disabled={!facecam}
              onChange={(checked) => patchReframe({ facecam_split: checked })}
            />

            {settings.reframe.facecam_split && facecam ? (
              <SliderRow
                label="Facecam panel height"
                value={settings.reframe.facecam_height}
                min={360}
                max={880}
                step={20}
                suffix="px"
                onChange={(value) => patchReframe({ facecam_height: value })}
              />
            ) : null}

            <div className="space-y-1.5">
              <Label>Tracking focus</Label>
              <Select
                value={settings.reframe.focus}
                onChange={(event) =>
                  patchReframe({ focus: event.target.value as ReframeSettings["focus"] })
                }
              >
                <option value="action" className="bg-[#150d22]">
                  Action — faces then motion
                </option>
                <option value="face" className="bg-[#150d22]">
                  Faces only
                </option>
                <option value="center" className="bg-[#150d22]">
                  Locked center crop
                </option>
              </Select>
            </div>

            <SliderRow
              label="Camera smoothing"
              value={Math.round(settings.reframe.smoothing * 100)}
              min={0}
              max={90}
              step={5}
              suffix="%"
              onChange={(value) => patchReframe({ smoothing: value / 100 })}
            />
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              Higher smoothing keeps the crop steadier on fast gameplay; lower values follow flicks
              more aggressively.
            </p>

            {project.analysis_summary ? (
              <div className="grid grid-cols-2 gap-2">
                <Metric label="Hype moments" value={String(project.analysis_summary.peak_count)} />
                <Metric
                  label="Audio"
                  value={project.analysis_summary.has_audio ? "detected" : "silent"}
                />
              </div>
            ) : null}
          </TabsContent>

          {/* -------------------------------- Effects -------------------------------- */}
          <TabsContent value="effects" className="mt-0 space-y-5">
            <ToggleRow
              label="Auto punch-ins"
              description="Snap zooms on loud reactions, placed from the audio energy curve."
              checked={settings.effects.punch_ins}
              onChange={(checked) => patchEffects({ punch_ins: checked })}
            />
            {settings.effects.punch_ins ? (
              <>
                <SliderRow
                  label="Zoom amount"
                  value={settings.effects.punch_in_zoom}
                  min={1.02}
                  max={1.5}
                  step={0.01}
                  format={(value) => `${value.toFixed(2)}×`}
                  onChange={(value) => patchEffects({ punch_in_zoom: value })}
                />
                <SliderRow
                  label="Max punch-ins"
                  value={settings.effects.punch_in_count}
                  min={0}
                  max={10}
                  step={1}
                  onChange={(value) => patchEffects({ punch_in_count: value })}
                />
                <ToggleRow
                  label="Motion blur on punch"
                  description="Blends two frames during each snap zoom for a whip feel."
                  checked={settings.effects.motion_blur}
                  onChange={(checked) => patchEffects({ motion_blur: checked })}
                  compact
                />
                <ToggleRow
                  label="White flash hits"
                  checked={settings.effects.flash}
                  onChange={(checked) => patchEffects({ flash: checked })}
                  compact
                />
              </>
            ) : null}

            <div className="my-1 h-px bg-white/[0.06]" />

            <ToggleRow
              label="Sound effects"
              description="Whoosh + thump layered on every punch-in."
              checked={settings.effects.sfx}
              onChange={(checked) => patchEffects({ sfx: checked })}
            />
            {settings.effects.sfx ? (
              <SliderRow
                label="SFX volume"
                value={Math.round(settings.effects.sfx_volume * 100)}
                min={0}
                max={120}
                step={5}
                suffix="%"
                onChange={(value) => patchEffects({ sfx_volume: value / 100 })}
              />
            ) : null}

            <SliderRow
              label="Saturation"
              value={settings.effects.saturation}
              min={0.8}
              max={1.4}
              step={0.02}
              format={(value) => `${Math.round(value * 100)}%`}
              onChange={(value) => patchEffects({ saturation: value })}
            />
            <ToggleRow
              label="Fade in"
              checked={settings.effects.fade_in}
              onChange={(checked) => patchEffects({ fade_in: checked })}
              compact
            />

            {peaks.length ? (
              <div className="space-y-1.5">
                <Label>Detected hype moments</Label>
                <div className="flex flex-wrap gap-1.5">
                  {peaks.map((peak, index) => (
                    <button
                      key={`${peak}-${index}`}
                      type="button"
                      onClick={() => onSeek(peak)}
                      className="inline-flex items-center gap-1 rounded-md border border-amber-400/25 bg-amber-400/10 px-1.5 py-0.5 font-mono text-[10px] text-amber-200 hover:bg-amber-400/20"
                    >
                      <Zap className="size-2.5" /> {timecode(peak)}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </TabsContent>

          {/* --------------------------------- Audio --------------------------------- */}
          <TabsContent value="audio" className="mt-0 space-y-5">
            <SliderRow
              label="Original audio"
              value={Math.round(settings.audio.original_volume * 100)}
              min={0}
              max={200}
              step={5}
              suffix="%"
              onChange={(value) => patchAudio({ original_volume: value / 100 })}
            />

            <div className="space-y-2 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
              <div className="flex items-center justify-between">
                <Label>Background music</Label>
                {project.has_music ? <Badge variant="success">Loaded</Badge> : null}
              </div>
              {project.has_music ? (
                <div className="space-y-2">
                  <p className="truncate text-xs text-muted-foreground">
                    {project.urls.music?.split("/").pop()?.split("?")[0]}
                  </p>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="flex-1" asChild>
                      <label className="cursor-pointer">
                        <Upload className="size-3.5" /> Replace
                        <input
                          type="file"
                          accept="audio/*"
                          className="hidden"
                          onChange={(event) => {
                            const file = event.target.files?.[0];
                            if (file) onMusicUpload(file);
                            event.target.value = "";
                          }}
                        />
                      </label>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={onMusicRemove}
                      disabled={musicBusy}
                      className="text-rose-300 hover:text-rose-200"
                    >
                      {musicBusy ? <Loader2 className="animate-spin" /> : <Trash2 className="size-3.5" />}
                    </Button>
                  </div>
                </div>
              ) : (
                <div>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">
                    Add a music bed under the stream audio. MP3, M4A, WAV.
                  </p>
                  <Button variant="outline" size="sm" className="mt-2 w-full" asChild>
                    <label className="cursor-pointer">
                      {musicBusy ? <Loader2 className="animate-spin" /> : <Upload className="size-3.5" />}
                      Upload music
                      <input
                        type="file"
                        accept="audio/*"
                        className="hidden"
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) onMusicUpload(file);
                          event.target.value = "";
                        }}
                      />
                    </label>
                  </Button>
                </div>
              )}
            </div>

            <SliderRow
              label="Music volume"
              value={Math.round(settings.audio.music_volume * 100)}
              min={0}
              max={100}
              step={1}
              suffix="%"
              disabled={!project.has_music}
              onChange={(value) => patchAudio({ music_volume: value / 100 })}
            />
            <ToggleRow
              label="Duck music under the mic"
              description="Sidechain compression pulls the bed down whenever the streamer speaks."
              checked={settings.audio.duck_music}
              disabled={!project.has_music}
              onChange={(checked) => patchAudio({ duck_music: checked })}
              compact
            />
          </TabsContent>

          {/* -------------------------------- Overlays -------------------------------- */}
          <TabsContent value="overlays" className="mt-0 space-y-4">
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" className="flex-1" onClick={() => addOverlay("text")}>
                <Plus className="size-3.5" /> Text
              </Button>
              <Button
                variant="secondary"
                size="sm"
                className="flex-1"
                onClick={() => addOverlay("emoji")}
                disabled={stickers.length === 0}
              >
                <Sparkles className="size-3.5" /> Sticker
              </Button>
            </div>

            {settings.overlays.length === 0 ? (
              <p className="rounded-xl border border-dashed border-white/10 px-3 py-6 text-center text-[11px] text-muted-foreground">
                Add meme text or a sticker at the playhead. It renders above the captions.
              </p>
            ) : (
              <div className="space-y-1.5">
                {settings.overlays.map((overlay) => (
                  <button
                    key={overlay.id}
                    type="button"
                    onClick={() => setSelectedOverlay(overlay.id)}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded-lg border px-2.5 py-2 text-left text-xs transition-colors",
                      selectedOverlay === overlay.id
                        ? "border-primary/50 bg-primary/10"
                        : "border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.05]",
                    )}
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      {overlay.kind === "emoji" ? (
                        stickers.find((sticker) => sticker.id === overlay.text) ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={mediaUrl(`/api/stickers/${overlay.text}.png`)}
                            alt=""
                            className="size-5"
                          />
                        ) : (
                          <Sparkles className="size-3.5 text-twitch-light" />
                        )
                      ) : (
                        <span className="size-2 rounded-full bg-twitch" />
                      )}
                      <span className="truncate font-medium">
                        {overlay.kind === "emoji" ? overlay.text : overlay.text || "Text"}
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-1 font-mono text-[10px] text-muted-foreground">
                      {timecode(overlay.start)}
                      <Trash2
                        className="size-3.5 hover:text-rose-400"
                        onClick={(event) => {
                          event.stopPropagation();
                          removeOverlay(overlay.id);
                        }}
                      />
                    </span>
                  </button>
                ))}
              </div>
            )}

            {activeOverlay ? (
              <div className="space-y-3 rounded-xl border border-white/[0.07] bg-black/20 p-3">
                {activeOverlay.kind === "text" ? (
                  <div className="space-y-1.5">
                    <Label>Text</Label>
                    <Input
                      value={activeOverlay.text}
                      onChange={(event) => updateOverlay(activeOverlay.id, { text: event.target.value })}
                      maxLength={48}
                      className="h-9"
                    />
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <Label>Sticker</Label>
                    <div className="grid max-h-36 grid-cols-8 gap-1 overflow-y-auto scrollbar-thin">
                      {stickers.map((sticker) => (
                        <button
                          key={sticker.id}
                          type="button"
                          onClick={() => updateOverlay(activeOverlay.id, { text: sticker.id })}
                          className={cn(
                            "flex aspect-square items-center justify-center rounded-md border p-1 transition-colors",
                            activeOverlay.text === sticker.id
                              ? "border-primary/60 bg-primary/20"
                              : "border-transparent hover:bg-white/10",
                          )}
                          title={sticker.id}
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={mediaUrl(sticker.url)} alt={sticker.id} className="size-5" />
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <SliderRow
                  label="Start"
                  value={activeOverlay.start}
                  min={0}
                  max={Math.max(1, duration)}
                  step={0.1}
                  format={(value) => timecode(value)}
                  onChange={(value) =>
                    updateOverlay(activeOverlay.id, {
                      start: value,
                      end: Math.max(value + 0.5, activeOverlay.end),
                    })
                  }
                />
                <SliderRow
                  label="End"
                  value={activeOverlay.end}
                  min={0.5}
                  max={Math.max(1, duration)}
                  step={0.1}
                  format={(value) => timecode(value)}
                  onChange={(value) =>
                    updateOverlay(activeOverlay.id, {
                      end: Math.max(value, activeOverlay.start + 0.5),
                    })
                  }
                />
                <SliderRow
                  label="Horizontal"
                  value={Math.round(activeOverlay.x * 100)}
                  min={5}
                  max={95}
                  step={1}
                  suffix="%"
                  onChange={(value) => updateOverlay(activeOverlay.id, { x: value / 100 })}
                />
                <SliderRow
                  label="Vertical"
                  value={Math.round(activeOverlay.y * 100)}
                  min={5}
                  max={95}
                  step={1}
                  suffix="%"
                  onChange={(value) => updateOverlay(activeOverlay.id, { y: value / 100 })}
                />
                <SliderRow
                  label="Size"
                  value={activeOverlay.size}
                  min={30}
                  max={220}
                  step={2}
                  suffix="px"
                  onChange={(value) => updateOverlay(activeOverlay.id, { size: value })}
                />
                {activeOverlay.kind === "text" ? (
                  <ColorField
                    label="Color"
                    value={activeOverlay.color}
                    onChange={(value) => updateOverlay(activeOverlay.id, { color: value })}
                  />
                ) : null}
              </div>
            ) : null}
          </TabsContent>

          {/* --------------------------------- Export -------------------------------- */}
          <TabsContent value="export" className="mt-0 space-y-4">
            <div className="space-y-2">
              {[
                { id: "tiktok", label: "TikTok", note: "1080×1920 · 8 Mbps · UI-safe" },
                { id: "shorts", label: "YouTube Shorts", note: "1080×1920 · 10 Mbps" },
                { id: "reels", label: "Instagram Reels", note: "1080×1920 · 8 Mbps" },
              ].map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() =>
                    onSettingsChange({ preset: preset.id as RenderSettings["preset"] })
                  }
                  className={cn(
                    "flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left transition-colors",
                    settings.preset === preset.id
                      ? "border-primary/60 bg-primary/10"
                      : "border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.05]",
                  )}
                >
                  <div>
                    <p className="text-sm font-medium">{preset.label}</p>
                    <p className="text-[10px] text-muted-foreground">{preset.note}</p>
                  </div>
                  <span
                    className={cn(
                      "size-4 rounded-full border",
                      settings.preset === preset.id
                        ? "border-twitch bg-twitch shadow-[0_0_0_3px_rgba(145,70,255,0.2)]"
                        : "border-white/25",
                    )}
                  />
                </button>
              ))}
            </div>

            <div className="space-y-1.5 rounded-xl border border-white/[0.06] bg-black/20 p-3 text-[11px] text-muted-foreground">
              <Row label="Trim" value={`${timecode(settings.trim.start)} → ${timecode(settings.trim.end ?? duration)}`} />
              <Row label="Resolution" value="1080 × 1920 · 30 fps" />
              <Row label="Captions" value={settings.captions.enabled && project.has_transcript ? "burned in" : "off"} />
              <Row label="Punch-ins" value={settings.effects.punch_ins ? `up to ${settings.effects.punch_in_count}` : "off"} />
              <Row label="Overlays" value={String(settings.overlays.length)} />
              <Row label="Music" value={project.has_music ? `${Math.round(settings.audio.music_volume * 100)}%` : "none"} />
            </div>

            <Button
              className="w-full"
              size="lg"
              onClick={onRenderFinal}
              disabled={busy || rendering}
            >
              {rendering && job?.kind === "render:final" ? (
                <>
                  <Loader2 className="animate-spin" /> Rendering {Math.round(job.progress * 100)}%
                </>
              ) : (
                <>
                  <Download /> Render final MP4
                </>
              )}
            </Button>
            <Button variant="outline" className="w-full" onClick={onRenderPreview} disabled={busy || rendering}>
              <Film /> Refresh preview
            </Button>

            {rendering && job ? (
              <Progress value={job.progress * 100} />
            ) : null}

            {project.renders.preview ? (
              <RenderRow
                title="Preview"
                meta={`${project.renders.preview.width}×${project.renders.preview.height} · ${formatBytes(project.renders.preview.size_bytes)}`}
                url={project.urls.preview}
                fileName={`${project.name}-preview.mp4`}
                stale={project.stale.preview}
              />
            ) : null}
            {project.renders.final ? (
              <RenderRow
                title="Final export"
                meta={`${project.renders.final.width}×${project.renders.final.height} · ${formatBytes(project.renders.final.size_bytes)} · ${formatDuration(project.renders.final.duration)}`}
                url={project.urls.final}
                fileName={`${project.name}-${settings.preset}.mp4`}
                stale={project.stale.final}
                primary
              />
            ) : null}

            <SharePanel project={project} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
  disabled,
  compact,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  compact?: boolean;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3", disabled && "opacity-50")}>
      <div className="min-w-0">
        <p className={cn("font-medium", compact ? "text-xs" : "text-sm")}>{label}</p>
        {description ? (
          <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">{description}</p>
        ) : null}
      </div>
      <Switch checked={checked} onCheckedChange={onChange} disabled={disabled} className="mt-0.5 shrink-0" />
    </div>
  );
}

function SliderRow({
  label,
  value,
  min,
  max,
  step,
  suffix,
  format,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  format?: (value: number) => string;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <div className={cn("space-y-1", disabled && "opacity-50")}>
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium text-muted-foreground">{label}</span>
        <span className="font-mono text-[11px] text-foreground/90">
          {format ? format(value) : `${value}${suffix ?? ""}`}
        </span>
      </div>
      <Slider
        value={[value]}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        onValueChange={(next) => onChange(next[0] ?? value)}
      />
    </div>
  );
}

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-1">
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <label className="flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-white/10 bg-black/25 px-1.5">
        <input
          type="color"
          value={value}
          onChange={(event) => onChange(event.target.value.toUpperCase())}
          className="size-6 cursor-pointer rounded"
        />
        <span className="truncate font-mono text-[10px] text-muted-foreground">{value}</span>
      </label>
    </div>
  );
}

function CaptionPreview({ style }: { style: CaptionStyle }) {
  return (
    <div className="relative aspect-[16/9] overflow-hidden rounded-xl border border-white/[0.08] bg-gradient-to-br from-[#251143] via-[#170a29] to-[#0c0614]">
      <div className="absolute inset-0 opacity-60 [background:radial-gradient(circle_at_75%_20%,rgba(255,62,165,0.28),transparent_45%),radial-gradient(circle_at_20%_75%,rgba(70,200,255,0.18),transparent_45%)]" />
      <div className="absolute inset-0 flex items-center justify-center px-4">
        <p
          className="text-center font-black leading-[0.95]"
          style={{
            fontSize: `${clamp(style.font_size / 9, 14, 30)}px`,
            color: style.text_color,
            WebkitTextStroke: `${Math.max(0.4, style.outline_width / 4)}px ${style.outline_color}`,
            letterSpacing: "0.01em",
            textTransform: style.uppercase ? "uppercase" : "none",
            background: style.background ? style.background_color : undefined,
            padding: style.background ? "6px 10px" : undefined,
            borderRadius: style.background ? "8px" : undefined,
            fontFamily:
              style.font === "Impact"
                ? "Impact, Haettenschweiler, sans-serif"
                : "Arial Black, Arial, sans-serif",
          }}
        >
          <span style={{ color: style.active_color }}>THIS</span> IS THE{" "}
          <span style={{ color: style.active_color }}>CRAZIEST</span> CLUTCH
        </p>
      </div>
      <span className="absolute bottom-1.5 left-2 text-[9px] uppercase tracking-widest text-white/40">
        Caption preview
      </span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-semibold">{value}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span>{label}</span>
      <span className="font-mono text-foreground/80">{value}</span>
    </div>
  );
}

function RenderRow({
  title,
  meta,
  url,
  fileName,
  stale,
  primary,
}: {
  title: string;
  meta: string;
  url?: string | null;
  fileName: string;
  stale?: boolean;
  primary?: boolean;
}) {
  const href = mediaUrl(url);
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] px-3 py-2.5">
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 text-xs font-semibold">
          {title}
          {stale ? <Badge variant="warning">stale</Badge> : null}
        </p>
        <p className="text-[10px] text-muted-foreground">{meta}</p>
      </div>
      {href ? (
        <Button variant={primary ? "default" : "outline"} size="sm" asChild>
          <a href={href} download={fileName}>
            <Download className="size-3.5" /> MP4
          </a>
        </Button>
      ) : null}
    </div>
  );
}
