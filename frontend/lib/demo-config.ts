import demoData from "@/public/demo/demo-data.json";
import type { Health, Project, PublicShare, Sticker } from "@/lib/types";

/**
 * Build-time switch for the read-only static demo.
 *
 * Kept free of client-only code because `next.config.mjs` and the server routes
 * (`generateStaticParams`) read these values during the build.
 */

export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "1";

export const DEMO_APP_NOTE =
  "This is a read-only preview. Rendering, transcription and imports run on your own machine in the ClipTok desktop app.";

export type DemoBundle = {
  generated_at: string;
  projects: Project[];
  share: PublicShare;
  health: Health;
  stickers: Sticker[];
};

export const demoBundle = demoData as unknown as DemoBundle;

/** Sample projects, in the order they appear in the library. */
export const demoProjects: Project[] = demoBundle.projects;

export const demoProjectIds = demoProjects.map((project) => project.id);

export const demoShareSlug = demoBundle.share.slug;
