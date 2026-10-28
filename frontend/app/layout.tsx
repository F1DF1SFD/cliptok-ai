import type { Metadata, Viewport } from "next";

import "./globals.css";
import { AppShell } from "@/components/app-shell";
import { ToastProvider } from "@/components/ui/toast";

export const metadata: Metadata = {
  title: "ClipTok AI — Twitch clips into viral shorts",
  description:
    "Turn Twitch clips into captioned TikToks, Shorts and Reels: Whisper captions, auto reframing, facecam layouts and one-click exports.",
};

export const viewport: Viewport = {
  themeColor: "#0b0714",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background font-sans text-foreground">
        <ToastProvider>
          <AppShell>{children}</AppShell>
        </ToastProvider>
      </body>
    </html>
  );
}
