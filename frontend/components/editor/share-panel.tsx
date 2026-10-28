"use client";

import * as React from "react";
import { Check, Copy, ExternalLink, Link2, Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { assetPath } from "@/lib/base-path";
import type { Project, ShareInfo } from "@/lib/types";

function publicUrl(share: ShareInfo): string {
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  return `${origin}${assetPath(share.path)}`;
}

export function SharePanel({ project }: { project: Project }) {
  const { toast } = useToast();
  const [share, setShare] = React.useState<ShareInfo | null>(project.share ?? null);
  const [busy, setBusy] = React.useState(false);
  const [copied, setCopied] = React.useState(false);
  const [link, setLink] = React.useState("");

  React.useEffect(() => {
    setShare(project.share ?? null);
  }, [project.share]);

  React.useEffect(() => {
    setLink(share ? publicUrl(share) : "");
  }, [share]);

  const hasRender = Boolean(project.renders.final || project.renders.preview);

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
      return true;
    } catch {
      toast({ title: "Copy it manually", description: value });
      return false;
    }
  };

  const create = async () => {
    setBusy(true);
    try {
      const { share: created } = await api.share(project.id);
      setShare(created);
      await copy(publicUrl(created));
      toast({
        title: "Share link copied",
        description: "Anyone with the link can watch and download this clip.",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "Couldn't create a link",
        description: error instanceof Error ? error.message : undefined,
        variant: "error",
      });
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    setBusy(true);
    try {
      await api.unshare(project.id);
      setShare(null);
      toast({ title: "Link turned off", description: "The clip is private again." });
    } catch (error) {
      toast({
        title: "Couldn't turn off the link",
        description: error instanceof Error ? error.message : undefined,
        variant: "error",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2 rounded-xl border border-white/[0.07] bg-gradient-to-br from-primary/10 to-transparent p-3">
      <div className="flex items-center gap-2">
        <Link2 className="size-3.5 text-primary" />
        <p className="text-xs font-semibold">Send it to someone</p>
      </div>
      <p className="text-[11px] leading-relaxed text-muted-foreground">
        {share
          ? "The link opens a clean watch page — no studio access, just the clip and a download button."
          : "Publish this clip to a private link anyone can watch, even without the app."}
      </p>

      {share ? (
        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <input
              readOnly
              value={link}
              onFocus={(event) => event.currentTarget.select()}
              className="h-8 min-w-0 flex-1 truncate rounded-lg border border-white/10 bg-black/30 px-2 font-mono text-[10px] text-foreground/80 outline-none"
            />
            <Button
              size="icon"
              variant="outline"
              className="size-8 shrink-0"
              onClick={() => void copy(link)}
              title="Copy link"
            >
              {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
            </Button>
            <Button size="icon" variant="outline" className="size-8 shrink-0" asChild title="Open">
              <a href={link || assetPath(share.path)} target="_blank" rel="noreferrer">
                <ExternalLink className="size-3.5" />
              </a>
            </Button>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Public · {share.quality === "final" ? "final export" : "preview"}
            </span>
            <button
              type="button"
              onClick={() => void revoke()}
              disabled={busy}
              className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground transition-colors hover:text-destructive disabled:opacity-50"
            >
              <Trash2 className="size-3" /> Turn off
            </button>
          </div>
        </div>
      ) : (
        <Button
          size="sm"
          variant="secondary"
          className="w-full"
          onClick={() => void create()}
          disabled={busy || !hasRender}
        >
          {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Link2 className="size-3.5" />}
          {hasRender ? "Create share link" : "Render a clip first"}
        </Button>
      )}
    </div>
  );
}
