"use client";

import * as React from "react";
import {
  Eye,
  EyeOff,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Volume2,
  VolumeX,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { mediaUrl } from "@/lib/api";
import type { Job, Project } from "@/lib/types";
import { cn, formatDuration } from "@/lib/utils";

interface Props {
  project: Project;
  mode: "preview" | "source";
  onModeChange: (mode: "preview" | "source") => void;
  job: Job | null;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  onTimeUpdate: (time: number) => void;
  onRequestRender: () => void;
  rendering: boolean;
}

export function PreviewPlayer({
  project,
  mode,
  onModeChange,
  job,
  videoRef,
  onTimeUpdate,
  onRequestRender,
  rendering,
}: Props) {
  const [playing, setPlaying] = React.useState(false);
  const [muted, setMuted] = React.useState(false);
  const [duration, setDuration] = React.useState(project.duration);
  const [current, setCurrent] = React.useState(0);
  const [safeZones, setSafeZones] = React.useState(false);

  const hasPreview = Boolean(project.urls.preview);
  const effectiveMode = hasPreview ? mode : "source";
  const src = mediaUrl(effectiveMode === "preview" ? project.urls.preview : project.urls.source);
  const poster = mediaUrl(project.urls.preview_thumbnail ?? project.urls.thumbnail);

  React.useEffect(() => {
    // Reset transport when the source switches (new render, source toggle, etc).
    setCurrent(0);
    setPlaying(false);
  }, [src]);

  React.useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const handlePlay = () => setPlaying(true);
    const handlePause = () => setPlaying(false);
    video.addEventListener("play", handlePlay);
    video.addEventListener("pause", handlePause);
    return () => {
      video.removeEventListener("play", handlePlay);
      video.removeEventListener("pause", handlePause);
    };
  }, [videoRef]);

  React.useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      const video = videoRef.current;
      if (!video) return;
      if (event.code === "Space") {
        event.preventDefault();
        if (video.paused) void video.play();
        else video.pause();
      }
      if (event.code === "ArrowLeft") video.currentTime = Math.max(0, video.currentTime - 1);
      if (event.code === "ArrowRight") video.currentTime = Math.min(video.duration || 0, video.currentTime + 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [videoRef]);

  const toggle = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) void video.play();
    else video.pause();
  };

  const seek = (value: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = value;
    setCurrent(value);
    onTimeUpdate(value);
  };

  const progress = duration > 0 ? (current / duration) * 100 : 0;

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Badge variant={effectiveMode === "preview" ? "default" : "secondary"}>
            {effectiveMode === "preview" ? "Preview render" : "Source"}
          </Badge>
          {project.stale.preview ? (
            <Badge variant="warning">Out of date</Badge>
          ) : null}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setSafeZones((value) => !value)}
            aria-label="Toggle safe zones"
            title="TikTok / Shorts UI safe zones"
          >
            {safeZones ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
          </Button>
          {hasPreview ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onModeChange(effectiveMode === "preview" ? "source" : "preview")}
            >
              {effectiveMode === "preview" ? "Original" : "Preview"}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="p-3">
        <div className="relative mx-auto aspect-[9/16] w-full max-w-[320px] overflow-hidden rounded-2xl border border-white/[0.08] bg-black safe-area-frame">
          {src ? (
            <video
              key={src}
              ref={videoRef}
              src={src}
              poster={poster}
              playsInline
              muted={muted}
              className="size-full bg-black object-contain"
              onLoadedMetadata={(event) => {
                const video = event.currentTarget;
                setDuration(video.duration || project.duration);
                video.currentTime = Math.min(0.15, video.duration || 0);
              }}
              onTimeUpdate={(event) => {
                const time = event.currentTarget.currentTime;
                setCurrent(time);
                onTimeUpdate(time);
              }}
              onClick={toggle}
            />
          ) : (
            <div className="flex size-full items-center justify-center text-xs text-muted-foreground">
              No video source
            </div>
          )}

          {safeZones ? (
            <div className="pointer-events-none absolute inset-0">
              <div className="absolute inset-x-0 top-0 h-[9%] border-b border-dashed border-white/25 bg-black/25" />
              <div className="absolute inset-x-0 bottom-0 h-[16%] border-t border-dashed border-white/25 bg-black/25" />
              <div className="absolute right-0 top-0 h-full w-[14%] border-l border-dashed border-white/15 bg-black/10" />
              <span className="absolute bottom-[17%] left-2 text-[9px] uppercase tracking-widest text-white/40">
                UI safe
              </span>
            </div>
          ) : null}

          {job && (job.status === "running" || job.status === "queued") ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/70 px-6 text-center backdrop-blur-sm">
              <Loader2 className="size-6 animate-spin text-twitch-light" />
              <div className="w-full max-w-[220px] space-y-1.5">
                <p className="text-xs font-semibold">
                  {job.kind === "transcribe"
                    ? "Transcribing with Whisper"
                    : job.kind === "analyze"
                      ? "Analyzing the action"
                      : "Rendering your short"}
                </p>
                <Progress value={job.progress * 100} />
                <p className="text-[10px] text-muted-foreground">
                  {job.message} · {Math.round(job.progress * 100)}%
                </p>
              </div>
            </div>
          ) : null}

          {!hasPreview && !rendering && !job ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-gradient-to-t from-black/90 via-black/40 to-transparent px-6 text-center">
              <p className="text-xs font-medium text-white/80">
                Render a preview to see captions, reframing and punch-ins.
              </p>
              <Button size="sm" onClick={onRequestRender}>
                <RefreshCw /> Render preview
              </Button>
            </div>
          ) : null}

          <div className="pointer-events-none absolute left-2 top-2 rounded-md bg-black/55 px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-white/80 backdrop-blur">
            {effectiveMode === "preview" ? `${project.settings.preset.toUpperCase()} 9:16` : `${project.width}×${project.height}`}
          </div>
        </div>

        <div className="mt-3 space-y-2">
          <div className="group relative h-1.5 cursor-pointer rounded-full bg-white/10"
            onClick={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              const ratio = (event.clientX - rect.left) / rect.width;
              seek(Math.max(0, Math.min(duration, ratio * duration)));
            }}
          >
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-twitch to-[#e879ff]"
              style={{ width: `${progress}%` }}
            />
            <div
              className="absolute top-1/2 size-3 -translate-y-1/2 rounded-full bg-white opacity-0 shadow transition-opacity group-hover:opacity-100"
              style={{ left: `calc(${progress}% - 6px)` }}
            />
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              <Button variant="secondary" size="icon-sm" onClick={toggle} aria-label="Play / pause">
                {playing ? <Pause className="size-3.5" /> : <Play className="size-3.5 translate-x-px" />}
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => seek(0)}
                aria-label="Restart"
                title="Back to start"
              >
                <RotateCcw className="size-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => {
                  setMuted((value) => !value);
                  if (videoRef.current) videoRef.current.muted = !muted;
                }}
                aria-label="Mute"
              >
                {muted ? <VolumeX className="size-3.5" /> : <Volume2 className="size-3.5" />}
              </Button>
            </div>
            <span className={cn("font-mono text-[11px] text-muted-foreground")}>
              {formatDuration(current)} / {formatDuration(duration || project.duration)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
