"use client";

import * as React from "react";
import { Crop, RotateCcw, Scissors, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { CaptionLine, Overlay, Trim } from "@/lib/types";
import { clamp, cn, timecode } from "@/lib/utils";

interface Props {
  duration: number;
  trim: Trim;
  onTrimChange: (trim: Trim) => void;
  waveform?: number[];
  peaks: number[];
  captionLines: CaptionLine[];
  overlays: Overlay[];
  currentTime: number;
  onSeek: (time: number) => void;
}

const MIN_CLIP = 1;

export function Timeline({
  duration,
  trim,
  onTrimChange,
  waveform,
  peaks,
  captionLines,
  overlays,
  currentTime,
  onSeek,
}: Props) {
  const trackRef = React.useRef<HTMLDivElement>(null);
  const [drag, setDrag] = React.useState<"start" | "end" | null>(null);
  const [scrubbing, setScrubbing] = React.useState(false);

  const total = Math.max(0.1, duration);
  const start = clamp(trim.start, 0, Math.max(0, total - MIN_CLIP));
  const end = clamp(trim.end ?? total, start + MIN_CLIP, total);
  const pct = (value: number) => `${(clamp(value, 0, total) / total) * 100}%`;

  const tickStep = total <= 15 ? 2 : total <= 40 ? 5 : total <= 120 ? 15 : 30;
  const ticks = React.useMemo(() => {
    const list: number[] = [];
    for (let t = 0; t <= total; t += tickStep) list.push(t);
    return list;
  }, [tickStep, total]);

  const bars = React.useMemo(() => {
    const count = 110;
    if (waveform && waveform.length > 2) {
      return Array.from({ length: count }, (_, index) => {
        const source = waveform[Math.min(waveform.length - 1, Math.floor((index / count) * waveform.length))];
        return clamp(source, 0.06, 1);
      });
    }
    return Array.from({ length: count }, () => 0.12);
  }, [waveform]);

  const timeFromEvent = React.useCallback(
    (clientX: number) => {
      const rect = trackRef.current?.getBoundingClientRect();
      if (!rect) return 0;
      return clamp(((clientX - rect.left) / rect.width) * total, 0, total);
    },
    [total],
  );

  React.useEffect(() => {
    if (!drag) return;
    const handleMove = (event: PointerEvent) => {
      const time = timeFromEvent(event.clientX);
      if (drag === "start") {
        onTrimChange({ start: Math.min(time, end - MIN_CLIP), end: trim.end });
      } else {
        onTrimChange({ start: trim.start, end: Math.max(time, start + MIN_CLIP) });
      }
    };
    const stop = () => setDrag(null);
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", stop);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", stop);
    };
  }, [drag, end, onTrimChange, start, timeFromEvent, trim.end, trim.start]);

  React.useEffect(() => {
    if (!scrubbing) return;
    const move = (event: PointerEvent) => onSeek(timeFromEvent(event.clientX));
    const stop = () => setScrubbing(false);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
  }, [onSeek, scrubbing, timeFromEvent]);

  return (
    <div className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Scissors className="size-3.5 text-twitch-light" />
          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Timeline
          </span>
          <span className="rounded-md border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {timecode(start)} → {timecode(end)}
          </span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onTrimChange({ start: 0, end: null })}
          disabled={start === 0 && end >= total}
        >
          <RotateCcw className="size-3" /> Reset trim
        </Button>
      </div>

      <div className="px-4 pb-3 pt-2">
        {/* Ruler */}
        <div
          ref={trackRef}
          className="relative h-6 cursor-pointer select-none"
          onPointerDown={(event) => {
            setScrubbing(true);
            onSeek(timeFromEvent(event.clientX));
          }}
        >
          {ticks.map((tick) => (
            <div key={tick} className="absolute top-0 h-full" style={{ left: pct(tick) }}>
              <div className="h-2 w-px bg-white/15" />
              <span className="absolute left-1 top-2 whitespace-nowrap text-[9px] tabular-nums text-muted-foreground/70">
                {timecode(tick).slice(0, 5)}
              </span>
            </div>
          ))}
        </div>

        {/* Video / audio track */}
        <div className="relative mt-1 h-[68px] overflow-hidden rounded-lg border border-white/[0.07] bg-black/40">
          <div className="absolute inset-0 flex items-end gap-[2px] px-[1px] pb-1">
            {bars.map((value, index) => (
              <div
                key={index}
                className={cn(
                  "flex-1 rounded-t-[1px]",
                  (index / bars.length) * total >= start && (index / bars.length) * total <= end
                    ? "bg-gradient-to-t from-twitch/70 to-twitch-light/80"
                    : "bg-white/10",
                )}
                style={{ height: `${Math.round(value * 78)}%` }}
              />
            ))}
          </div>

          {/* trim shading */}
          <div className="pointer-events-none absolute inset-y-0 left-0 bg-black/60" style={{ width: pct(start) }} />
          <div
            className="pointer-events-none absolute inset-y-0 right-0 bg-black/60"
            style={{ width: `calc(100% - ${pct(end)})` }}
          />

          {/* punch-in markers */}
          {peaks.slice(0, 10).map((peak, index) => (
            <div
              key={`${peak}-${index}`}
              className="pointer-events-none absolute top-1 -translate-x-1/2 text-amber-300"
              style={{ left: pct(peak) }}
              title={`Hype moment at ${timecode(peak)}`}
            >
              <Zap className="size-3 drop-shadow" fill="currentColor" />
            </div>
          ))}

          {/* trim handles */}
          <div
            className="absolute inset-y-0 z-10 w-5 -translate-x-1/2 cursor-ew-resize"
            style={{ left: pct(start) }}
            onPointerDown={(event) => {
              event.stopPropagation();
              setDrag("start");
            }}
          >
            <div className="absolute inset-y-0 left-1/2 w-[3px] -translate-x-1/2 bg-twitch shadow-[0_0_12px_rgba(145,70,255,0.9)]" />
            <div className="absolute left-1/2 top-1/2 h-9 w-4 -translate-x-1/2 -translate-y-1/2 rounded-md border border-twitch/60 bg-[#1a0f2c] shadow">
              <span className="absolute inset-y-1.5 left-[5px] w-px bg-white/40" />
              <span className="absolute inset-y-1.5 right-[5px] w-px bg-white/40" />
            </div>
          </div>
          <div
            className="absolute inset-y-0 z-10 w-5 -translate-x-1/2 cursor-ew-resize"
            style={{ left: pct(end) }}
            onPointerDown={(event) => {
              event.stopPropagation();
              setDrag("end");
            }}
          >
            <div className="absolute inset-y-0 left-1/2 w-[3px] -translate-x-1/2 bg-twitch shadow-[0_0_12px_rgba(145,70,255,0.9)]" />
            <div className="absolute left-1/2 top-1/2 h-9 w-4 -translate-x-1/2 -translate-y-1/2 rounded-md border border-twitch/60 bg-[#1a0f2c] shadow">
              <span className="absolute inset-y-1.5 left-[5px] w-px bg-white/40" />
              <span className="absolute inset-y-1.5 right-[5px] w-px bg-white/40" />
            </div>
          </div>

          {/* playhead */}
          <div className="pointer-events-none absolute inset-y-0 z-20 w-px bg-white/90" style={{ left: pct(currentTime) }}>
            <div className="absolute -left-[3px] top-0 size-[7px] rounded-full bg-white" />
          </div>

          <div className="pointer-events-none absolute bottom-1 left-2 rounded bg-black/50 px-1 text-[9px] tabular-nums text-white/70">
            {timecode(currentTime)}
          </div>
        </div>

        {/* Captions track */}
        <div className="relative mt-1 h-8 overflow-hidden rounded-lg border border-white/[0.07] bg-white/[0.02]">
          <div className="absolute left-2 top-1/2 -translate-y-1/2 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/70">
            CC
          </div>
          {captionLines.slice(0, 160).map((line, index) => (
            <button
              type="button"
              key={`${line.start}-${index}`}
              onClick={() => onSeek(line.start)}
              className="absolute top-1 h-6 overflow-hidden rounded border border-emerald-400/25 bg-emerald-400/15 px-1.5 text-left text-[9px] leading-6 text-emerald-100/90 hover:bg-emerald-400/25"
              style={{
                left: `calc(${pct(line.start)} + 0px)`,
                width: `max(10px, calc(${((line.end - line.start) / total) * 100}% - 1px))`,
              }}
              title={line.text}
            >
              <span className="truncate">{line.text}</span>
            </button>
          ))}
          {captionLines.length === 0 ? (
            <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-[10px] text-muted-foreground">
              No captions yet — run Whisper transcription
            </span>
          ) : null}
        </div>

        {/* Overlay track */}
        <div className="relative mt-1 h-7 overflow-hidden rounded-lg border border-white/[0.07] bg-white/[0.02]">
          <div className="absolute left-2 top-1/2 -translate-y-1/2 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/70">
            Overlays
          </div>
          {overlays.map((overlay) => (
            <div
              key={overlay.id}
              className="absolute top-1 flex h-5 max-w-[140px] items-center gap-1 overflow-hidden rounded border border-primary/30 bg-primary/20 px-1.5 text-[9px] text-twitch-light"
              style={{
                left: pct(overlay.start),
                width: `max(24px, calc(${((overlay.end - overlay.start) / total) * 100}% - 1px))`,
              }}
              title={`${overlay.kind === "emoji" ? "Sticker" : "Text"}: ${overlay.text}`}
            >
              {overlay.kind === "emoji" ? <Crop className="size-2.5 shrink-0" /> : null}
              <span className="truncate">{overlay.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
