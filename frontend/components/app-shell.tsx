"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Clapperboard,
  Github,
  Layers,
  Menu,
  Plus,
  Scissors,
  Sparkles,
  X,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { DEMO_MODE } from "@/lib/demo";
import type { Health } from "@/lib/types";
import { cn } from "@/lib/utils";

const NAV = [
  { label: "Studio", href: "/", icon: Clapperboard },
  { label: "Library", href: "/#library", icon: Layers },
  { label: "Workflow", href: "/#workflow", icon: Zap },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);
  const [health, setHealth] = React.useState<Health | null>(null);
  const [offline, setOffline] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((payload) => {
        if (!cancelled) setHealth(payload);
      })
      .catch(() => {
        if (!cancelled) setOffline(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const enginesOk = health?.status === "ok";

  // Shared clip links are a standalone watch page for people who don't own the studio.
  if (pathname?.startsWith("/s/")) return <>{children}</>;

  return (
    <div className="relative flex min-h-screen">
      <div className="pointer-events-none fixed inset-0 -z-10 grid-bg opacity-60" />

      {/* Mobile top bar */}
      <div className="fixed inset-x-0 top-0 z-40 flex h-14 items-center justify-between border-b border-white/[0.06] bg-[#0b0714]/90 px-4 backdrop-blur-xl lg:hidden">
        <Link href="/" className="flex items-center gap-2">
          <LogoMark />
          <span className="display text-lg tracking-wide">ClipTok AI</span>
        </Link>
        <Button variant="ghost" size="icon-sm" onClick={() => setOpen((value) => !value)} aria-label="Menu">
          {open ? <X /> : <Menu />}
        </Button>
      </div>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[240px] flex-col border-r border-white/[0.06] bg-[#0a0612]/90 px-4 py-6 backdrop-blur-2xl transition-transform duration-300 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <Link href="/" className="mb-8 flex items-center gap-2.5 px-1">
          <LogoMark />
          <div className="leading-none">
            <span className="display block text-xl tracking-wide">ClipTok</span>
            <span className="text-[10px] font-semibold uppercase tracking-[0.34em] text-twitch-light/80">
              AI Studio
            </span>
          </div>
        </Link>

        <nav className="flex flex-col gap-1">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" || pathname.startsWith("/editor") : false;
            const Icon = item.icon;
            return (
              <Link
                key={item.label}
                href={item.href}
                className={cn(
                  "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all",
                  active
                    ? "bg-primary/15 text-foreground shadow-[inset_0_0_0_1px_rgba(145,70,255,0.25)]"
                    : "text-muted-foreground hover:bg-white/[0.05] hover:text-foreground",
                )}
              >
                <Icon className={cn("size-4", active ? "text-twitch-light" : "text-muted-foreground")} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-6 rounded-2xl border border-white/[0.07] bg-gradient-to-b from-primary/15 to-transparent p-3.5">
          <div className="flex items-center gap-2 text-xs font-semibold">
            <Sparkles className="size-3.5 text-twitch-light" />
            New project
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
            Drop a Twitch clip or MP4 and ship a captioned short in minutes.
          </p>
          <Link href="/#import" className="mt-3 block">
            <Button size="sm" className="w-full">
              <Plus className="size-3.5" /> Create clip
            </Button>
          </Link>
        </div>

        <div className="mt-auto space-y-3 pt-6">
          <div
            className="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[11px]"
            title={
              offline
                ? "Backend not reachable"
                : health
                  ? `Whisper: ${health.capabilities.whisper ? health.whisper_model : "missing"} · FFmpeg: ${health.capabilities.ffmpeg ? "ready" : "missing"} · yt-dlp: ${health.capabilities.ytdlp ? "ready" : "missing"}`
                  : "Checking engines"
            }
          >
            <span className="relative flex size-2">
              <span
                className={cn(
                  "absolute inline-flex size-full animate-ping rounded-full opacity-75",
                  offline ? "bg-rose-400" : enginesOk ? "bg-emerald-400" : "bg-amber-400",
                )}
              />
              <span
                className={cn(
                  "relative inline-flex size-2 rounded-full",
                  offline ? "bg-rose-500" : enginesOk ? "bg-emerald-500" : "bg-amber-500",
                )}
              />
            </span>
            <span className="truncate text-muted-foreground">
              {DEMO_MODE
                ? "Demo · sample only"
                : offline
                  ? "API offline"
                  : enginesOk
                    ? "Engines online"
                    : health
                      ? "Setup needed"
                      : "Checking…"}
            </span>
          </div>
          <div className="flex items-center justify-between px-1 text-[11px] text-muted-foreground/70">
            <span className="inline-flex items-center gap-1">
              <Scissors className="size-3" /> v1.0
            </span>
            {DEMO_MODE ? (
              <span className="inline-flex items-center gap-1">
                <Sparkles className="size-3" /> Sample build
              </span>
            ) : (
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 transition-colors hover:text-foreground"
              >
                <Github className="size-3" /> Docs
              </a>
            )}
          </div>
        </div>
      </aside>

      {open ? (
        <button
          type="button"
          aria-label="Close menu"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
        />
      ) : null}

      <main className="relative min-w-0 flex-1 pt-14 lg:ml-[240px] lg:pt-0">
        {DEMO_MODE ? (
          <div className="border-b border-white/[0.06] bg-primary/10 px-4 py-2 text-center text-[11px] text-twitch-light lg:px-8">
            <span className="font-semibold">Read-only demo</span> — the clips are pre-rendered by
            ClipTok&apos;s real pipeline. Editing works; rendering and imports run in the desktop app.
          </div>
        ) : null}
        {children}
      </main>
    </div>
  );
}

function LogoMark() {
  return (
    <div className="relative flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-twitch via-[#b04bff] to-[#ff3ea5] shadow-[0_8px_24px_-8px_rgba(145,70,255,0.9)]">
      <Clapperboard className="size-4 text-white" strokeWidth={2.4} />
      <span className="absolute -right-0.5 -top-0.5 size-2 rounded-full bg-emerald-400 ring-2 ring-[#0a0612]" />
    </div>
  );
}
