"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  Captions,
  Check,
  Clapperboard,
  Clock3,
  Crop,
  Download,
  Film,
  Flame,
  Layers,
  Loader2,
  Scissors,
  Sparkles,
  Wand2,
  Zap,
} from "lucide-react";

import { ImportPanel } from "@/components/dashboard/import-panel";
import { ProjectCard } from "@/components/dashboard/project-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import type { Health, Project } from "@/lib/types";
import { formatDuration } from "@/lib/utils";

const WORKFLOW = [
  {
    icon: Clapperboard,
    title: "Drop a clip",
    copy: "Paste a Twitch clip URL or drag in an MP4. We pull the video and metadata automatically.",
  },
  {
    icon: Captions,
    title: "Whisper transcribes",
    copy: "Word-by-word timestamps from Whisper, grouped into punchy TikTok caption lines.",
  },
  {
    icon: Crop,
    title: "Auto reframe",
    copy: "Face-aware tracking crops to 9:16. Facecams get their own panel so nothing is lost.",
  },
  {
    icon: Download,
    title: "Export & post",
    copy: "Punch-ins, stickers and a music bed in one render, sized for TikTok, Shorts and Reels.",
  },
];

const FEATURES = [
  {
    icon: Flame,
    title: "Karaoke captions",
    copy: "Bold white text, hard black outline and the spoken word lighting up in your accent colour.",
  },
  {
    icon: Wand2,
    title: "Smart punch-ins",
    copy: "Loud reactions trigger snap zooms and optional whooshes, synced to the loudness curve.",
  },
  {
    icon: Layers,
    title: "Facecam aware",
    copy: "Stable corner-face detection keeps gameplay on top and the streamer underneath.",
  },
];

export default function DashboardPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [projects, setProjects] = React.useState<Project[] | null>(null);
  const [health, setHealth] = React.useState<Health | null>(null);
  const [offline, setOffline] = React.useState(false);

  const load = React.useCallback(async () => {
    try {
      const [projectList, healthPayload] = await Promise.all([api.listProjects(), api.health()]);
      setProjects(projectList);
      setHealth(healthPayload);
      setOffline(false);
    } catch (error) {
      setOffline(true);
      setProjects([]);
      if (error instanceof ApiError && error.status !== 0) {
        toast({ title: "Could not load projects", description: error.message, variant: "error" });
      }
    }
  }, [toast]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const rendered = projects?.filter((project) => project.renders.preview || project.renders.final).length ?? 0;
  const captioned = projects?.filter((project) => project.has_transcript).length ?? 0;
  const totalSeconds = projects?.reduce((sum, project) => sum + (project.duration || 0), 0) ?? 0;

  const missing = health
    ? [
        !health.capabilities.ffmpeg && "FFmpeg",
        !health.capabilities.whisper && "faster-whisper",
        !health.capabilities.opencv && "OpenCV",
        !health.capabilities.ytdlp && "yt-dlp",
      ].filter(Boolean)
    : [];

  return (
    <div className="pb-20">
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-white/[0.06] px-5 pb-14 pt-10 sm:px-8 lg:px-12 lg:pb-20 lg:pt-16">
        <div className="pointer-events-none absolute left-1/2 top-0 h-[420px] w-[820px] -translate-x-1/2 rounded-full bg-primary/20 blur-[120px]" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-[11px] font-semibold text-twitch-light">
              <Sparkles className="size-3.5" />
              Twitch → Shorts, on autopilot
            </div>
            <h1 className="mt-5 max-w-xl text-balance text-4xl font-black leading-[1.02] tracking-tight sm:text-5xl lg:text-[56px]">
              Turn one <span className="gradient-text">Twitch clip</span> into a week of shorts.
            </h1>
            <p className="mt-5 max-w-lg text-[15px] leading-relaxed text-muted-foreground">
              Paste a clip, and ClipTok writes word-perfect captions, reframes the action to vertical,
              punches in on the loud moments and exports platform-ready MP4s.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Button size="lg" asChild>
                <a href="#import">
                  Clip a stream <ArrowRight />
                </a>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <a href="#workflow">
                  <Zap className="text-twitch-light" /> See the workflow
                </a>
              </Button>
            </div>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-[11px] text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <Check className="size-3.5 text-emerald-400" /> Whisper word timings
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Check className="size-3.5 text-emerald-400" /> Facecam split layouts
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Check className="size-3.5 text-emerald-400" /> 1080×1920 exports
              </span>
            </div>
          </div>

          {/* Decorative vertical preview */}
          <div className="relative mx-auto hidden w-full max-w-[330px] lg:block">
            <div className="absolute -inset-6 rounded-[36px] bg-gradient-to-b from-primary/30 via-fuchsia-500/10 to-transparent blur-2xl" />
            <div className="relative overflow-hidden rounded-[30px] border border-white/10 bg-black shadow-[0_40px_120px_-40px_rgba(145,70,255,0.8)]">
              <div className="relative aspect-[9/16] overflow-hidden bg-gradient-to-br from-[#2a1250] via-[#1b0b34] to-[#0d0716]">
                <div className="absolute inset-0 opacity-70 [background:radial-gradient(circle_at_70%_20%,rgba(255,62,165,0.35),transparent_45%),radial-gradient(circle_at_20%_70%,rgba(70,200,255,0.25),transparent_45%)]" />
                <div className="absolute inset-x-0 top-0 flex items-center justify-between p-4 text-[10px] font-semibold uppercase tracking-[0.2em] text-white/60">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="size-1.5 rounded-full bg-rose-500" /> LIVE CLIP
                  </span>
                  <span>01:12</span>
                </div>

                <div className="absolute left-1/2 top-[38%] -translate-x-1/2">
                  <div className="flex size-16 animate-float items-center justify-center rounded-2xl border border-white/15 bg-white/[0.07] backdrop-blur">
                    <Clapperboard className="size-7 text-white/80" />
                  </div>
                </div>

                <div className="absolute inset-x-4 top-[62%] text-center">
                  <p className="display text-[30px] leading-[1.05] text-white [text-shadow:_3px_3px_0_#000,_-2px_-2px_0_#000,_2px_-2px_0_#000,_-2px_2px_0_#000]">
                    THIS IS THE
                  </p>
                  <p className="display text-[34px] leading-[1.05] text-white [text-shadow:_3px_3px_0_#000,_-2px_-2px_0_#000,_2px_-2px_0_#000,_-2px_2px_0_#000]">
                    <span className="text-[#FFE600]">CRAZIEST</span> CLUTCH
                  </p>
                </div>

                <div className="absolute inset-x-4 bottom-5 flex items-center justify-between text-[10px] text-white/60">
                  <span className="rounded-md bg-black/50 px-2 py-1 backdrop-blur">9:16 · TikTok</span>
                  <span className="rounded-md bg-black/50 px-2 py-1 backdrop-blur">1080p</span>
                </div>
              </div>
            </div>

            <div className="absolute -left-8 top-16 animate-float rounded-xl border border-white/10 bg-[#150d22]/90 px-3 py-2 text-[11px] font-medium shadow-xl backdrop-blur">
              <span className="inline-flex items-center gap-1.5">
                <Captions className="size-3.5 text-twitch-light" /> Word-by-word captions
              </span>
            </div>
            <div
              className="absolute -right-6 bottom-20 animate-float rounded-xl border border-white/10 bg-[#150d22]/90 px-3 py-2 text-[11px] font-medium shadow-xl backdrop-blur"
              style={{ animationDelay: "1.2s" }}
            >
              <span className="inline-flex items-center gap-1.5">
                <Crop className="size-3.5 text-emerald-400" /> Auto reframe 9:16
              </span>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-5 sm:px-8 lg:px-12">
        {offline ? (
          <div className="mt-6 flex flex-col gap-3 rounded-2xl border border-amber-400/25 bg-amber-400/[0.06] p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-400" />
              <div>
                <p className="text-sm font-semibold text-amber-200">The ClipTok API is offline</p>
                <p className="mt-0.5 text-xs text-amber-200/70">
                  Start it with <code className="kbd">cd backend && .venv/bin/uvicorn app.main:app --port 8000</code>
                </p>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={() => void load()}>
              Retry
            </Button>
          </div>
        ) : missing.length > 0 ? (
          <div className="mt-6 flex items-start gap-3 rounded-2xl border border-amber-400/25 bg-amber-400/[0.06] p-4">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-400" />
            <div className="text-xs text-amber-200/80">
              <p className="text-sm font-semibold text-amber-200">Missing engine: {missing.join(", ")}</p>
              <p className="mt-1">
                Install backend requirements with{" "}
                <code className="kbd">backend/.venv/bin/pip install -r backend/requirements.txt</code>.
              </p>
            </div>
          </div>
        ) : null}

        {/* Stats */}
        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Clips", value: String(projects?.length ?? 0), icon: Film },
            { label: "Rendered", value: String(rendered), icon: Clapperboard },
            { label: "Captioned", value: String(captioned), icon: Captions },
            { label: "Runtime", value: formatDuration(totalSeconds), icon: Clock3 },
          ].map((stat) => (
            <div key={stat.label} className="panel px-4 py-3.5">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  {stat.label}
                </p>
                <stat.icon className="size-3.5 text-twitch-light/70" />
              </div>
              <p className="mt-1.5 text-2xl font-bold tracking-tight">{stat.value}</p>
            </div>
          ))}
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <section id="import" className="scroll-mt-24">
            <ImportPanel
              onCreated={(project) => router.push(`/editor/${project.id}`)}
              maxUploadBytes={health?.limits.max_upload_bytes ?? 512 * 1024 * 1024}
              maxClipSeconds={health?.limits.max_clip_seconds ?? 600}
              twitchReady={health ? health.capabilities.ytdlp : true}
            />
          </section>

          <section className="panel p-5 sm:p-6">
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-twitch-light">
              Shorts presets
            </p>
            <h2 className="mt-1 text-lg font-semibold tracking-tight">Export once, post everywhere</h2>
            <div className="mt-4 space-y-2">
              {(health?.presets ?? [
                { id: "tiktok", label: "TikTok", width: 1080, height: 1920, fps: 30, video_bitrate: "8M", description: "1080x1920 — 8 Mbps" },
                { id: "shorts", label: "YouTube Shorts", width: 1080, height: 1920, fps: 30, video_bitrate: "10M", description: "1080x1920 — 10 Mbps" },
                { id: "reels", label: "Instagram Reels", width: 1080, height: 1920, fps: 30, video_bitrate: "8M", description: "1080x1920 — 8 Mbps" },
              ]).map((preset) => (
                <div
                  key={preset.id}
                  className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5"
                >
                  <div>
                    <p className="text-sm font-medium">{preset.label}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {preset.width}×{preset.height} · {preset.fps}fps · {preset.video_bitrate}
                    </p>
                  </div>
                  <Badge variant="outline">H.264</Badge>
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-2 rounded-xl border border-white/[0.06] bg-black/20 p-3 text-[11px] text-muted-foreground">
              <Scissors className="size-3.5 shrink-0 text-twitch-light" />
              Renders are written to your local project folder — nothing uploads to a third party.
            </div>
          </section>
        </div>

        {/* Library */}
        <section id="library" className="mt-12 scroll-mt-24">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-twitch-light">
                Library
              </p>
              <h2 className="mt-1 text-2xl font-bold tracking-tight">Your clips</h2>
            </div>
            <Button variant="ghost" size="sm" onClick={() => void load()}>
              <Loader2 className={projects === null ? "animate-spin" : "hidden"} /> Refresh
            </Button>
          </div>

          {projects === null ? (
            <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {[0, 1, 2].map((index) => (
                <div key={index} className="panel overflow-hidden">
                  <div className="skeleton aspect-video rounded-none" />
                  <div className="space-y-2 p-3">
                    <div className="skeleton h-3 w-2/3" />
                    <div className="skeleton h-2.5 w-1/3" />
                  </div>
                </div>
              ))}
            </div>
          ) : projects.length === 0 ? (
            <div className="mt-5 flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.015] px-6 py-14 text-center">
              <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/15">
                <Clapperboard className="size-6 text-twitch-light" />
              </div>
              <h3 className="mt-4 text-base font-semibold">No clips yet</h3>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                Paste a Twitch clip URL above or drop an MP4 to create your first vertical short.
              </p>
              <Button className="mt-5" asChild>
                <a href="#import">
                  Import a clip <ArrowRight />
                </a>
              </Button>
            </div>
          ) : (
            <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {projects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onDeleted={(id) => setProjects((current) => current?.filter((item) => item.id !== id) ?? [])}
                />
              ))}
            </div>
          )}
        </section>

        {/* Workflow */}
        <section id="workflow" className="mt-16 scroll-mt-24">
          <div className="text-center">
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-twitch-light">Workflow</p>
            <h2 className="mx-auto mt-2 max-w-2xl text-balance text-2xl font-bold tracking-tight sm:text-3xl">
              From stream to scroll-stopper in four steps
            </h2>
          </div>
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {WORKFLOW.map((step, index) => (
              <div key={step.title} className="panel relative p-5">
                <span className="absolute right-4 top-4 display text-3xl text-white/[0.07]">
                  0{index + 1}
                </span>
                <div className="flex size-10 items-center justify-center rounded-xl bg-primary/15">
                  <step.icon className="size-4 text-twitch-light" />
                </div>
                <h3 className="mt-4 text-sm font-semibold">{step.title}</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{step.copy}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-12 grid gap-3 sm:grid-cols-3">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5">
              <feature.icon className="size-5 text-twitch-light" />
              <h3 className="mt-3 text-sm font-semibold">{feature.title}</h3>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{feature.copy}</p>
            </div>
          ))}
        </section>

        <footer className="mt-14 flex flex-col items-center justify-between gap-3 border-t border-white/[0.06] pt-6 text-[11px] text-muted-foreground sm:flex-row">
          <span>ClipTok AI · local-first video studio</span>
          <span>Whisper · OpenCV · FFmpeg</span>
        </footer>
      </div>
    </div>
  );
}
