"use client";

import * as React from "react";
import Link from "next/link";
import { Download, Link2Off, Play, Scissors } from "lucide-react";

import { mediaUrl } from "@/lib/api";
import type { PublicShare } from "@/lib/types";
import { formatDuration } from "@/lib/utils";

export function WatchClient({ slug, share }: { slug: string; share: PublicShare | null }) {
  const [muted, setMuted] = React.useState(true);

  if (!share) {
    return (
      <main className="relative flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(145,70,255,0.22),transparent_55%)]" />
        <Link2Off className="size-8 text-muted-foreground" />
        <h1 className="text-lg font-semibold">This clip link is off</h1>
        <p className="max-w-xs text-sm text-muted-foreground">
          The link <span className="font-mono text-xs">{slug}</span> was turned off or the clip was
          removed.
        </p>
        <Link
          href="/"
          className="text-xs font-medium text-primary underline-offset-4 hover:underline"
        >
          Open ClipTok AI
        </Link>
      </main>
    );
  }

  const video = mediaUrl(share.video_url);
  const poster = mediaUrl(share.thumbnail_url);
  const download = mediaUrl(share.download_url);

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#08050f] text-foreground">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_-10%,rgba(145,70,255,0.30),transparent_55%),radial-gradient(circle_at_15%_80%,rgba(255,62,165,0.16),transparent_45%)]" />
      <div className="relative mx-auto flex min-h-screen w-full max-w-md flex-col items-center justify-center gap-5 px-4 py-8">
        <div className="relative w-full overflow-hidden rounded-[26px] border border-white/10 bg-black shadow-[0_30px_80px_-20px_rgba(145,70,255,0.55)]">
          <div className="aspect-[9/16] w-full">
            {video ? (
              <video
                key={video}
                src={video}
                poster={poster}
                className="h-full w-full object-contain"
                autoPlay
                muted={muted}
                loop
                playsInline
                controls
                onPlay={() => setMuted(false)}
              />
            ) : (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                <Play className="size-8" />
              </div>
            )}
          </div>
        </div>

        <div className="w-full space-y-1 text-center">
          <h1 className="line-clamp-2 text-base font-semibold">{share.title}</h1>
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {formatDuration(share.duration)} ·{" "}
            {share.width && share.height ? `${share.width}×${share.height}` : "9:16"}
            {share.captions ? " · captions on" : ""}
          </p>
        </div>

        <div className="flex w-full flex-col gap-2">
          <a
            href={download}
            download
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Download className="size-4" /> Download MP4
          </a>
          <button
            type="button"
            onClick={() => setMuted((value) => !value)}
            className="text-[11px] text-muted-foreground transition-colors hover:text-foreground"
          >
            {muted ? "Sound is off — tap to unmute" : "Mute"}
          </button>
        </div>

        <div className="mt-2 flex items-center gap-1.5 text-[10px] text-muted-foreground/70">
          <Scissors className="size-3" />
          <Link href="/" className="underline-offset-4 hover:text-foreground hover:underline">
            Made with ClipTok AI
          </Link>
        </div>
      </div>
    </main>
  );
}
