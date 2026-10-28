"use client";

import * as React from "react";
import { Captions, Loader2, Search, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { CaptionLine, Job, Project } from "@/lib/types";
import { cn, timecode } from "@/lib/utils";

interface Props {
  project: Project;
  captionLines: CaptionLine[];
  currentTime: number;
  onSeek: (time: number) => void;
  onTranscribe: () => void;
  job: Job | null;
}

export function TranscriptPanel({
  project,
  captionLines,
  currentTime,
  onSeek,
  onTranscribe,
  job,
}: Props) {
  const [query, setQuery] = React.useState("");
  const containerRef = React.useRef<HTMLDivElement>(null);
  const busy = job?.kind === "transcribe" && (job.status === "running" || job.status === "queued");

  const filtered = React.useMemo(() => {
    if (!query.trim()) return captionLines;
    const needle = query.toLowerCase();
    return captionLines.filter((line) => line.text.toLowerCase().includes(needle));
  }, [captionLines, query]);

  React.useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const active = container.querySelector<HTMLElement>("[data-active='true']");
    if (active) {
      const top = active.offsetTop - container.clientHeight / 2 + active.clientHeight / 2;
      container.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    }
  }, [currentTime]);

  return (
    <div className="panel flex h-full min-h-[260px] flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Captions className="size-3.5 text-twitch-light" />
          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Transcript
          </span>
          {project.has_transcript ? (
            <Badge variant="secondary">{project.transcript?.word_count ?? 0} words</Badge>
          ) : null}
        </div>
        {project.has_transcript ? (
          <div className="relative w-32 sm:w-40">
            <Search className="pointer-events-none absolute left-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search"
              className="h-7 rounded-lg pl-7 text-[11px]"
            />
          </div>
        ) : null}
      </div>

      <div ref={containerRef} className="relative min-h-0 flex-1 overflow-y-auto p-2 scrollbar-thin">
        {!project.has_transcript ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-4 py-8 text-center">
            <div className="flex size-11 items-center justify-center rounded-xl bg-primary/15">
              <Sparkles className="size-5 text-twitch-light" />
            </div>
            <div>
              <p className="text-sm font-semibold">Captions make the clip</p>
              <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                Whisper transcribes your clip with word-level timing. The first run downloads the
                model once, then it stays cached.
              </p>
            </div>
            <Button size="sm" onClick={onTranscribe} disabled={busy}>
              {busy ? (
                <>
                  <Loader2 className="animate-spin" /> {Math.round((job?.progress ?? 0) * 100)}%
                </>
              ) : (
                <>
                  <Captions /> Transcribe clip
                </>
              )}
            </Button>
          </div>
        ) : filtered.length === 0 ? (
          <p className="px-3 py-8 text-center text-xs text-muted-foreground">No lines match “{query}”.</p>
        ) : (
          <div className="space-y-0.5 pb-2">
            {filtered.map((line, index) => {
              const active = currentTime >= line.start && currentTime < line.end;
              return (
                <button
                  key={`${line.start}-${index}`}
                  type="button"
                  data-active={active}
                  onClick={() => onSeek(line.start)}
                  className={cn(
                    "flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors",
                    active ? "bg-primary/15" : "hover:bg-white/[0.05]",
                  )}
                >
                  <span
                    className={cn(
                      "mt-0.5 shrink-0 font-mono text-[9px] tabular-nums",
                      active ? "text-twitch-light" : "text-muted-foreground/60",
                    )}
                  >
                    {timecode(line.start)}
                  </span>
                  <span className="text-[12px] leading-snug">
                    {line.words.map((word, wordIndex) => {
                      const speaking =
                        currentTime >= word.start && currentTime < Math.max(word.end, word.start + 0.02);
                      return (
                        <span
                          key={`${word.start}-${wordIndex}`}
                          className={cn(
                            "transition-colors",
                            speaking ? "font-semibold text-twitch-light" : "text-foreground/85",
                          )}
                        >
                          {word.word}{" "}
                        </span>
                      );
                    })}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
