import type { Metadata } from "next";

import { WatchClient } from "@/components/share/watch-client";
import type { PublicShare } from "@/lib/types";

// Used by the desktop / local-server build (see `pageExtensions` in
// next.config.mjs). Share links must be resolved per request so turning a link
// off takes effect immediately, hence force-dynamic.
export const dynamic = "force-dynamic";

const API_ORIGIN = (process.env.CLIPTOK_API_ORIGIN ?? "http://127.0.0.1:8000").replace(/\/$/, "");

async function loadShare(slug: string): Promise<PublicShare | null> {
  try {
    const response = await fetch(`${API_ORIGIN}/api/share/${encodeURIComponent(slug)}`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as PublicShare;
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const share = await loadShare(slug);
  if (!share) return { title: "Clip unavailable — ClipTok AI" };
  return {
    title: `${share.title} — ClipTok AI`,
    description: `A ${Math.round(share.duration)}s vertical clip made with ClipTok AI.`,
  };
}

export default async function SharePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const share = await loadShare(slug);
  return <WatchClient slug={slug} share={share} />;
}
