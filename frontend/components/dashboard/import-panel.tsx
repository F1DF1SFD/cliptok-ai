"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  CloudUpload,
  FileVideo,
  Link2,
  Loader2,
  MonitorPlay,
  Sparkles,
  UploadCloud,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { DEMO_MODE } from "@/lib/demo";
import { demoProjectIds } from "@/lib/demo-config";
import type { Project } from "@/lib/types";
import { cn, formatBytes } from "@/lib/utils";

const ACCEPTED = [".mp4", ".mov", ".webm", ".mkv", ".m4v"];

interface Props {
  onCreated: (project: Project) => void;
  maxUploadBytes: number;
  maxClipSeconds: number;
  twitchReady: boolean;
}

export function ImportPanel({ onCreated, maxUploadBytes, maxClipSeconds, twitchReady }: Props) {
  const { toast } = useToast();
  const [tab, setTab] = React.useState("twitch");
  const [url, setUrl] = React.useState("");
  const [importing, setImporting] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);
  const [progress, setProgress] = React.useState(0);
  const [fileName, setFileName] = React.useState<string | null>(null);
  const [dragging, setDragging] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  // The static demo has no encoder, so uploading a file would only fail. Point
  // visitors at the pre-rendered project instead of pretending to work.
  if (DEMO_MODE) {
    return (
      <div className="panel relative overflow-hidden p-5 sm:p-6">
        <div className="pointer-events-none absolute -right-16 -top-16 size-48 rounded-full bg-primary/25 blur-3xl" />
        <div className="relative">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-twitch-light">
                New project
              </p>
              <h2 className="mt-1 text-lg font-semibold tracking-tight">Bring in a clip</h2>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] font-medium text-muted-foreground">
              <MonitorPlay className="size-3 text-twitch-light" /> Demo build
            </span>
          </div>

          <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-white/15 bg-black/20 px-4 py-7 text-center">
            <div className="flex size-11 items-center justify-center rounded-xl bg-white/[0.06]">
              <FileVideo className="size-5 text-twitch-light" />
            </div>
            <p className="text-sm font-semibold">Uploads are off in this preview</p>
            <p className="max-w-xs text-[11px] leading-relaxed text-muted-foreground">
              Whisper, OpenCV and FFmpeg need a local machine. The desktop app runs the full
              pipeline on your own hardware — nothing is uploaded anywhere.
            </p>
          </div>

          <Button className="mt-3 w-full" size="lg" asChild>
            <Link href={`/editor/${demoProjectIds[0]}/`}>
              Open the sample project <ArrowRight />
            </Link>
          </Button>
          <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
            The sample was rendered by ClipTok itself: word-by-word captions, 9:16 reframing and
            punch-ins, from a 10-second landscape clip.
          </p>
        </div>
      </div>
    );
  }

  const submitUrl = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!url.trim() || importing) return;
    setImporting(true);
    try {
      const project = await api.importTwitch(url.trim());
      toast({
        title: "Clip imported",
        description: `${project.name} — ${Math.round(project.duration)}s ready to edit.`,
        variant: "success",
      });
      onCreated(project);
    } catch (error) {
      toast({
        title: "Could not import that clip",
        description: error instanceof ApiError ? error.message : "Unexpected error.",
        variant: "error",
      });
    } finally {
      setImporting(false);
    }
  };

  const handleFile = async (file: File) => {
    const dot = file.name.lastIndexOf(".");
    const extension = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
    if (!ACCEPTED.includes(extension)) {
      toast({ title: "Unsupported file", description: "Use MP4, MOV, WebM or MKV.", variant: "error" });
      return;
    }
    if (file.size > maxUploadBytes) {
      toast({
        title: "File too large",
        description: `Keep uploads under ${formatBytes(maxUploadBytes)}.`,
        variant: "error",
      });
      return;
    }
    setFileName(file.name);
    setUploading(true);
    setProgress(0);
    try {
      const project = await api.upload(file, setProgress);
      toast({ title: "Video uploaded", description: "Opening the editor…", variant: "success" });
      onCreated(project);
    } catch (error) {
      toast({
        title: "Upload failed",
        description: error instanceof ApiError ? error.message : "Unexpected error.",
        variant: "error",
      });
      setFileName(null);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="panel relative overflow-hidden p-5 sm:p-6">
      <div className="pointer-events-none absolute -right-16 -top-16 size-48 rounded-full bg-primary/25 blur-3xl" />
      <div className="relative">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-twitch-light">
              New project
            </p>
            <h2 className="mt-1 text-lg font-semibold tracking-tight">Bring in a clip</h2>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] font-medium text-muted-foreground">
            <Sparkles className="size-3 text-twitch-light" /> Auto captions
          </span>
        </div>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="w-full">
            <TabsTrigger value="twitch" className="flex-1">
              <Link2 className="size-3.5" /> Twitch URL
            </TabsTrigger>
            <TabsTrigger value="upload" className="flex-1">
              <UploadCloud className="size-3.5" /> Upload MP4
            </TabsTrigger>
          </TabsList>

          <TabsContent value="twitch">
            <form onSubmit={submitUrl} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="twitch-url">Clip or VOD link</Label>
                <div className="relative">
                  <Link2 className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="twitch-url"
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                    placeholder="https://clips.twitch.tv/FancyClipSlug or twitch.tv/streamer/clip/..."
                    className="pl-10"
                    autoComplete="off"
                    spellCheck={false}
                    disabled={importing}
                  />
                </div>
              </div>
              <Button type="submit" className="w-full" size="lg" disabled={importing || !url.trim() || !twitchReady}>
                {importing ? (
                  <>
                    <Loader2 className="animate-spin" /> Pulling clip from Twitch…
                  </>
                ) : (
                  <>
                    Import clip <ArrowRight />
                  </>
                )}
              </Button>
              {!twitchReady ? (
                <p className="text-[11px] leading-relaxed text-amber-300/90">
                  yt-dlp was not found. Install it with <code className="kbd">brew install yt-dlp</code> to
                  import Twitch links, or upload an MP4 instead.
                </p>
              ) : (
                <p className="text-[11px] leading-relaxed text-muted-foreground">
                  Clips up to {Math.round(maxClipSeconds / 60)} minutes. We fetch video + metadata with
                  yt-dlp, no Twitch API key required.
                </p>
              )}
            </form>
          </TabsContent>

          <TabsContent value="upload">
            <div
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
              }}
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                const file = event.dataTransfer.files?.[0];
                if (file) void handleFile(file);
              }}
              className={cn(
                "group flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-7 text-center transition-all",
                dragging
                  ? "border-primary bg-primary/10"
                  : "border-white/15 bg-black/20 hover:border-primary/60 hover:bg-primary/[0.06]",
                uploading && "pointer-events-none opacity-80",
              )}
            >
              <div className="flex size-11 items-center justify-center rounded-xl bg-white/[0.06] transition-colors group-hover:bg-primary/20">
                {uploading ? (
                  <CloudUpload className="size-5 animate-pulse text-twitch-light" />
                ) : (
                  <FileVideo className="size-5 text-twitch-light" />
                )}
              </div>
              <div className="space-y-0.5">
                <p className="text-sm font-semibold">
                  {uploading ? fileName : "Drop a clip here, or browse"}
                </p>
                <p className="text-[11px] text-muted-foreground">
                  MP4 · MOV · WebM · MKV — up to {formatBytes(maxUploadBytes)}
                </p>
              </div>
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPTED.join(",")}
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void handleFile(file);
                  event.target.value = "";
                }}
              />
            </div>
            {uploading ? (
              <div className="mt-3 space-y-1.5">
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>Uploading</span>
                  <span>{progress}%</span>
                </div>
                <Progress value={progress} />
              </div>
            ) : (
              <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
                Already have an export? Upload the raw gameplay and let ClipTok handle the vertical cut.
              </p>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
