"use client";

import * as React from "react";
import Link from "next/link";
import {
  Captions,
  Download,
  Film,
  Loader2,
  Play,
  Trash2,
  TrendingUp,
  Upload,
  Twitch as TwitchIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { api, ApiError, mediaUrl } from "@/lib/api";
import type { Project } from "@/lib/types";
import { cn, formatDuration, relativeTime } from "@/lib/utils";

export function ProjectCard({
  project,
  onDeleted,
}: {
  project: Project;
  onDeleted: (id: string) => void;
}) {
  const { toast } = useToast();
  const [deleting, setDeleting] = React.useState(false);
  const render = project.renders.final ?? project.renders.preview;
  const thumbnail = mediaUrl(project.urls.preview_thumbnail ?? project.urls.thumbnail);
  const downloadUrl = mediaUrl(project.urls.final ?? project.urls.preview);

  const remove = async () => {
    setDeleting(true);
    try {
      await api.deleteProject(project.id);
      toast({ title: "Project deleted", variant: "success" });
      onDeleted(project.id);
    } catch (error) {
      toast({
        title: "Could not delete project",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
      setDeleting(false);
    }
  };

  return (
    <div className="group panel panel-hover overflow-hidden">
      <Link href={`/editor/${project.id}`} className="relative block aspect-video overflow-hidden">
        {thumbnail ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumbnail}
            alt={project.name}
            className="size-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
          />
        ) : (
          <div className="flex size-full items-center justify-center bg-gradient-to-br from-[#1a1030] via-[#120a1f] to-[#0d0716]">
            <Film className="size-8 text-white/20" />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-transparent opacity-90" />

        <div className="absolute left-3 top-3 flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary" className="backdrop-blur-md">
            {project.source_kind === "twitch" ? <TwitchIcon className="size-3" /> : <Upload className="size-3" />}
            {project.source_kind === "twitch" ? "Twitch" : "Upload"}
          </Badge>
          {project.has_transcript ? (
            <Badge variant="success" className="backdrop-blur-md">
              <Captions className="size-3" /> Captioned
            </Badge>
          ) : null}
          {render ? (
            <Badge variant="default" className="backdrop-blur-md">
            {project.renders.final ? "Final" : "Preview"}
            </Badge>
          ) : null}
        </div>

        <span className="absolute right-3 top-3 rounded-md bg-black/65 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-white/90 backdrop-blur">
          {formatDuration(project.duration)}
        </span>

        <div className="absolute inset-x-0 bottom-0 flex items-end justify-between p-3">
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-white drop-shadow">{project.name}</h3>
            <p className="mt-0.5 text-[11px] text-white/60">
              {project.width}×{project.height} · {relativeTime(project.updated_at)}
            </p>
          </div>
          <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/10 text-white opacity-0 backdrop-blur transition-all group-hover:opacity-100">
            <Play className="size-4 translate-x-px" fill="currentColor" />
          </span>
        </div>
      </Link>

      <div className="flex items-center justify-between gap-2 px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2 text-[11px] text-muted-foreground">
          {project.analysis_summary?.facecam_detected ? (
            <Badge variant="outline" className="gap-1">
              <TrendingUp className="size-3" /> Facecam
            </Badge>
          ) : (
            <span className="inline-flex items-center gap-1">
              <TrendingUp className="size-3" />
              {project.analysis_summary?.peak_count ?? 0} hype moments
            </span>
          )}
          {project.active_job ? (
            <span className="inline-flex items-center gap-1 text-twitch-light">
              <Loader2 className="size-3 animate-spin" />
              {Math.round(project.active_job.progress * 100)}%
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-0.5">
          <Button asChild variant="ghost" size="icon-sm" aria-label="Open in editor">
            <Link href={`/editor/${project.id}`}>
              <TrendingUp className="size-4" />
            </Link>
          </Button>
          {downloadUrl ? (
            <Button asChild variant="ghost" size="icon-sm" aria-label="Download export">
              <a href={downloadUrl} download={`${project.name}.mp4`}>
                <Download className="size-4" />
              </a>
            </Button>
          ) : null}
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Delete project" className="hover:text-rose-400">
                <Trash2 className="size-4" />
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogTitle>Delete this project?</DialogTitle>
              <DialogDescription>
                {project.name} and its renders will be removed from disk. This cannot be undone.
              </DialogDescription>
              <div className="mt-6 flex justify-end gap-2">
                <DialogClose asChild>
                  <Button variant="ghost">Cancel</Button>
                </DialogClose>
                <Button
                  variant="destructive"
                  onClick={() => void remove()}
                  disabled={deleting}
                  className={cn(deleting && "opacity-80")}
                >
                  {deleting ? <Loader2 className="animate-spin" /> : <Trash2 />} Delete project
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>
    </div>
  );
}
