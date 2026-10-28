import type { Metadata } from "next";

import { WatchClient } from "@/components/share/watch-client";
import { demoBundle, demoShareSlug } from "@/lib/demo-config";
import type { PublicShare } from "@/lib/types";

// Static demo build only (see `pageExtensions` in next.config.mjs): the one
// sample share page is rendered at build time and shipped as plain HTML.
export function generateStaticParams() {
  return [{ slug: demoShareSlug }];
}

function loadShare(slug: string): PublicShare | null {
  return slug === demoShareSlug ? demoBundle.share : null;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const share = loadShare(slug);
  if (!share) return { title: "Clip unavailable — ClipTok AI" };
  return {
    title: `${share.title} — ClipTok AI`,
    description: `A ${Math.round(share.duration)}s vertical clip made with ClipTok AI.`,
  };
}

export default async function SharePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <WatchClient slug={slug} share={loadShare(slug)} />;
}
