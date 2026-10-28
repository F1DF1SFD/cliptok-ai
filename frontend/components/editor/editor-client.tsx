"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  Captions,
  Check,
  Download,
  ExternalLink,
  Loader2,
  RefreshCw,
  Twitch as TwitchIcon,
  Upload,
  Zap,
} from "lucide-react";

import { PreviewPlayer } from "@/components/editor/preview-player";
import { SettingsPanel } from "@/components/editor/settings-panel";
import { Timeline } from "@/components/editor/timeline";
import { TranscriptPanel } from "@/components/editor/transcript-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { DEMO_APP_NOTE, DEMO_MODE } from "@/lib/demo";
import { useJobPolling } from "@/lib/hooks";
import type { Health, Job, Project, RenderSettings, Sticker } from "@/lib/types";
import { cn, formatDuration } from "@/lib/utils";

const FALLBACK_FONTS = ["Arial Black", "Impact", "Arial Bold", "Arial Rounded Bold"];

export function EditorClient() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id ?? "";
  const { toast } = useToast();

  const [project, setProject] = React.useState<Project | null>(null);
  const [settings, setSettings] = React.useState<RenderSettings | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [jobId, setJobId] = React.useState<string | null>(null);
  const [mode, setMode] = React.useState<"preview" | "source">("preview");
  const [currentTime, setCurrentTime] = React.useState(0);
  const [stickers, setStickers] = React.useState<Sticker[]>([]);
  const [fonts, setFonts] = React.useState<string[]>(FALLBACK_FONTS);
  const [musicBusy, setMusicBusy] = React.useState(false);
  const [saveState, setSaveState] = React.useState<"idle" | "saving" | "saved" | "error">("idle");
  const [name, setName] = React.useState("");

  const videoRef = React.useRef<HTMLVideoElement | null>(null);
  const savedRef = React.useRef<string | null>(null);
  const initializedRef = React.useRef(false);

  const loadProject = React.useCallback(
    async (options?: { adoptSettings?: boolean }) => {
      try {
        const payload = await api.getProject(projectId);
        setProject(payload);
        setName(payload.name);
        if (options?.adoptSettings || !initializedRef.current) {
          setSettings(payload.settings);
          savedRef.current = JSON.stringify(payload.settings);
          initializedRef.current = true;
        }
        if (!payload.renders.preview && !payload.renders.final) setMode("source");
        setError(null);
      } catch (caught) {
        const message = caught instanceof ApiError ? caught.message : "Could not load this project.";
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [projectId],
  );

  React.useEffect(() => {
    initializedRef.current = false;
    savedRef.current = null;
    void loadProject({ adoptSettings: true });
  }, [loadProject]);

  React.useEffect(() => {
    let cancelled = false;
    void Promise.allSettled([api.health(), api.stickers()]).then(([healthResult, stickerResult]) => {
      if (cancelled) return;
      if (healthResult.status === "fulfilled") {
        const payload = healthResult.value as Health;
        if (payload.fonts?.length) setFonts(payload.fonts);
      }
      if (stickerResult.status === "fulfilled") {
        setStickers((stickerResult.value as { stickers: Sticker[] }).stickers);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Adopt a job that was already running (page reload, second tab, ...).
  React.useEffect(() => {
    if (project?.active_job && !jobId) setJobId(project.active_job.id);
  }, [project, jobId]);

  // Debounced auto-save of the settings draft.
  React.useEffect(() => {
    if (!settings || !project) return;
    const serialized = JSON.stringify(settings);
    if (savedRef.current === null) {
      savedRef.current = serialized;
      return;
    }
    if (serialized === savedRef.current) return;
    setSaveState("saving");
    const timer = setTimeout(async () => {
      try {
        await api.updateProject(project.id, { settings });
        savedRef.current = serialized;
        setSaveState("saved");
        setTimeout(() => setSaveState((state) => (state === "saved" ? "idle" : state)), 1800);
      } catch (caught) {
        setSaveState("error");
        toast({
          title: "Could not save changes",
          description: caught instanceof ApiError ? caught.message : undefined,
          variant: "error",
        });
      }
    }, 650);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings, project?.id]);

  const ensureSaved = React.useCallback(async () => {
    if (!settings || !project) return;
    const serialized = JSON.stringify(settings);
    if (savedRef.current === serialized) return;
    await api.updateProject(project.id, { settings });
    savedRef.current = serialized;
  }, [project, settings]);

  const job = useJobPolling(jobId, {
    onDone: async (finished: Job) => {
      setJobId(null);
      if (finished.kind.startsWith("render")) setMode("preview");
      await loadProject();
      if (finished.kind === "transcribe") {
        toast({ title: "Captions ready", description: "Word-level timing added to the timeline.", variant: "success" });
      } else if (finished.kind === "analyze") {
        toast({ title: "Analysis refreshed", description: "Reframing tracks updated.", variant: "success" });
      } else if (finished.kind === "render:final") {
        toast({ title: "Final export ready", description: "Download the MP4 from the Export tab.", variant: "success" });
      } else if (finished.kind === "render:preview") {
        toast({ title: "Preview rendered", variant: "success" });
      }
    },
    onError: (failed: Job) => {
      setJobId(null);
      toast({
        title: failed.kind.startsWith("render") ? "Render failed" : "Something went wrong",
        description: failed.error ?? "Check the backend logs for details.",
        variant: "error",
      });
    },
  });

  const busy = Boolean(jobId);

  const patchSettings = (patch: Partial<RenderSettings>) =>
    setSettings((current) => (current ? { ...current, ...patch } : current));

  const runJob = async (kind: "transcribe" | "analyze" | "render:preview" | "render:final") => {
    if (!project) return;
    if (DEMO_MODE) {
      toast({
        title: "Processing runs in the desktop app",
        description: DEMO_APP_NOTE,
        variant: "info",
      });
      return;
    }
    try {
      await ensureSaved();
      const started =
        kind === "transcribe"
          ? await api.transcribe(project.id)
          : kind === "analyze"
            ? await api.analyze(project.id)
            : await api.render(project.id, kind === "render:final" ? "final" : "preview");
      setJobId(started.id);
      toast({
        title:
          kind === "transcribe"
            ? "Transcribing with Whisper"
            : kind === "analyze"
              ? "Analyzing the clip"
              : kind === "render:final"
                ? "Rendering final export"
                : "Rendering preview",
        description: kind === "render:final" ? "1080×1920 encode — this can take a minute." : undefined,
        variant: "info",
      });
    } catch (caught) {
      toast({
        title: "Could not start that job",
        description: caught instanceof ApiError ? caught.message : undefined,
        variant: "error",
      });
    }
  };

  const saveName = async () => {
    if (!project) return;
    const trimmed = name.trim();
    if (!trimmed || trimmed === project.name) return;
    try {
      const updated = await api.updateProject(project.id, { name: trimmed });
      setProject(updated);
      setName(updated.name);
    } catch (caught) {
      toast({
        title: "Could not rename project",
        description: caught instanceof ApiError ? caught.message : undefined,
        variant: "error",
      });
    }
  };

  const uploadMusic = async (file: File) => {
    if (!project) return;
    if (DEMO_MODE) {
      toast({ title: "Not available in the preview", description: DEMO_APP_NOTE, variant: "info" });
      return;
    }
    setMusicBusy(true);
    try {
      const updated = await api.uploadMusic(project.id, file);
      setProject(updated);
      toast({ title: "Music added", variant: "success" });
    } catch (caught) {
      toast({
        title: "Could not add music",
        description: caught instanceof ApiError ? caught.message : undefined,
        variant: "error",
      });
    } finally {
      setMusicBusy(false);
    }
  };

  const removeMusic = async () => {
    if (!project) return;
    if (DEMO_MODE) {
      toast({ title: "Not available in the preview", description: DEMO_APP_NOTE, variant: "info" });
      return;
    }
    setMusicBusy(true);
    try {
      const updated = await api.removeMusic(project.id);
      setProject(updated);
      toast({ title: "Music removed" });
    } catch (caught) {
      toast({
        title: "Could not remove music",
        description: caught instanceof ApiError ? caught.message : undefined,
        variant: "error",
      });
    } finally {
      setMusicBusy(false);
    }
  };

  // Captions, overlays and peaks live on the source timeline; the rendered
  // preview starts at the trim point, so seek through this offset.
  const clipOffset = mode === "preview" ? settings?.trim.start ?? 0 : 0;
  const playhead = currentTime + clipOffset;

  const seek = (sourceTime: number) => {
    const target = Math.max(0, sourceTime - clipOffset);
    const video = videoRef.current;
    if (video) video.currentTime = Math.min(target, video.duration || target);
    setCurrentTime(target);
  };

  if (loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-sm text-muted-foreground">
          <Loader2 className="size-5 animate-spin text-twitch-light" />
          Loading project…
        </div>
      </div>
    );
  }

  if (error || !project || !settings) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-6 py-24 text-center">
        <div className="flex size-12 items-center justify-center rounded-2xl bg-rose-500/15">
          <AlertTriangle className="size-5 text-rose-400" />
        </div>
        <div>
          <h1 className="text-lg font-semibold">This project could not be opened</h1>
          <p className="mt-1 text-sm text-muted-foreground">{error ?? "Project not found."}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link href="/">
              <ArrowLeft /> Back to studio
            </Link>
          </Button>
          <Button onClick={() => void loadProject()}>
            <RefreshCw /> Retry
          </Button>
        </div>
      </div>
    );
  }

  const duration = project.duration || 0;
  const captionLines = project.caption_lines ?? [];
  const peaks = project.analysis_summary?.peaks ?? [];
  const waveform = project.analysis_summary?.waveform;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-14 z-30 border-b border-white/[0.06] bg-[#0b0714]/85 backdrop-blur-xl lg:top-0">
        <div className="mx-auto flex w-full max-w-[1500px] flex-wrap items-center gap-3 px-4 py-3">
          <Button variant="ghost" size="icon-sm" asChild aria-label="Back to studio">
            <Link href="/">
              <ArrowLeft />
            </Link>
          </Button>

          <div className="min-w-0 flex-1">
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              onBlur={() => void saveName()}
              onKeyDown={(event) => {
                if (event.key === "Enter") event.currentTarget.blur();
              }}
              className="h-8 border-transparent bg-transparent px-1 text-base font-semibold shadow-none hover:border-white/10 focus-visible:border-white/15"
            />
            <div className="mt-0.5 flex flex-wrap items-center gap-2 pl-1 text-[11px] text-muted-foreground">
              <Badge variant="secondary" className="gap-1">
                {project.source_kind === "twitch" ? <TwitchIcon className="size-3" /> : <Upload className="size-3" />}
                {project.source_kind === "twitch" ? "Twitch" : "Upload"}
              </Badge>
              <span className="tabular-nums">
                {formatDuration(duration)} · {project.width}×{project.height}
              </span>
              <span
                className={cn(
                  "inline-flex items-center gap-1",
                  saveState === "error" ? "text-rose-400" : "text-muted-foreground",
                )}
              >
                {saveState === "saving" ? (
                  <>
                    <Loader2 className="size-3 animate-spin" /> Saving
                  </>
                ) : saveState === "saved" ? (
                  <>
                    <Check className="size-3 text-emerald-400" /> Saved
                  </>
                ) : saveState === "error" ? (
                  "Save failed"
                ) : null}
              </span>
              {project.source_url ? (
                <a
                  href={project.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-muted-foreground/80 hover:text-twitch-light"
                >
                  <ExternalLink className="size-3" /> Source
                </a>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {!project.has_transcript ? (
              <Button variant="outline" size="sm" onClick={() => void runJob("transcribe")} disabled={busy}>
                {job?.kind === "transcribe" && job.status === "running" ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <Captions />
                )}
                Transcribe
              </Button>
            ) : null}
            <Button variant="outline" size="sm" onClick={() => void runJob("render:preview")} disabled={busy}>
              {busy ? <Loader2 className="animate-spin" /> : <RefreshCw />} Preview
            </Button>
            <Button size="sm" onClick={() => void runJob("render:final")} disabled={busy}>
              {job?.kind === "render:final" && job.status === "running" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Download />
              )}
              Export
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-[1500px] flex-1 gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_390px]">
        <div className="min-w-0 space-y-4">
          <div className="grid gap-4 md:grid-cols-[340px_minmax(0,1fr)]">
            <PreviewPlayer
              project={project}
              mode={mode}
              onModeChange={setMode}
              job={job}
              videoRef={videoRef}
              onTimeUpdate={setCurrentTime}
              onRequestRender={() => void runJob("render:preview")}
              rendering={busy}
            />
            <TranscriptPanel
              project={project}
              captionLines={captionLines}
              currentTime={playhead}
              onSeek={seek}
              onTranscribe={() => void runJob("transcribe")}
              job={job}
            />
          </div>

          <Timeline
            duration={duration}
            trim={settings.trim}
            onTrimChange={(trim) => patchSettings({ trim })}
            waveform={waveform}
            peaks={peaks}
            captionLines={captionLines}
            overlays={settings.overlays}
            currentTime={playhead}
            onSeek={seek}
          />

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="panel px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                Clip length
              </p>
              <p className="mt-1 text-lg font-semibold tabular-nums">
                {formatDuration(settings.trim.end ? settings.trim.end - settings.trim.start : duration)}
              </p>
            </div>
            <div className="panel px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                Hype moments
              </p>
              <p className="mt-1 flex items-center gap-1.5 text-lg font-semibold tabular-nums">
                <Zap className="size-4 text-amber-300" /> {peaks.length}
              </p>
            </div>
            <div className="panel px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                Last render
              </p>
              <p className="mt-1 text-lg font-semibold">
                {project.renders.final
                  ? "Final · 1080p"
                  : project.renders.preview
                    ? "Preview · 540p"
                    : "Not yet"}
              </p>
            </div>
          </div>
        </div>

        <div className="min-w-0 lg:sticky lg:top-[84px] lg:h-[calc(100vh-100px)]">
          <SettingsPanel
            project={project}
            settings={settings}
            fonts={fonts}
            stickers={stickers}
            duration={duration}
            currentTime={playhead}
            job={job}
            rendering={busy}
            musicBusy={musicBusy}
            onSettingsChange={patchSettings}
            onRenderPreview={() => void runJob("render:preview")}
            onRenderFinal={() => void runJob("render:final")}
            onAnalyze={() => void runJob("analyze")}
            onTranscribe={() => void runJob("transcribe")}
            onMusicUpload={(file) => void uploadMusic(file)}
            onMusicRemove={() => void removeMusic()}
            onSeek={seek}
          />
        </div>
      </div>
    </div>
  );
}
