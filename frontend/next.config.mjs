/** @type {import('next').NextConfig} */
const API_ORIGIN = (process.env.CLIPTOK_API_ORIGIN ?? "http://127.0.0.1:8000").replace(/\/$/, "");

// The static demo (NEXT_PUBLIC_DEMO_MODE=1) has no backend, so it exports plain
// files for any free static host. Everything else keeps the standalone server
// that scripts/package.sh ships in the downloadable app.
const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "1";

// GitHub Pages project sites live under /<repo>/; user sites live at the root.
const BASE_PATH = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
  output: DEMO ? "export" : "standalone",
  trailingSlash: DEMO,
  ...(BASE_PATH ? { basePath: BASE_PATH } : {}),
  // A static export can't contain a force-dynamic route, and the app can't use a
  // prerendered share page (turning a link off has to take effect immediately).
  // Each build therefore only sees its own share-page implementation.
  pageExtensions: DEMO ? ["demo.tsx", "tsx", "ts"] : ["app.tsx", "tsx", "ts"],
  // No next/image usage: keeping the optimizer off means the build never pulls
  // a platform-specific sharp binary, so one build serves macOS and Windows.
  images: { unoptimized: true },
};

// The studio talks to its own origin; Next proxies /api to the FastAPI process.
// That keeps one public URL working behind LAN addresses and tunnels. Static
// exports have no server to rewrite with, so the key is only added for the app.
if (!DEMO) {
  nextConfig.rewrites = async () => [
    { source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` },
    { source: "/media/:path*", destination: `${API_ORIGIN}/api/media/:path*` },
  ];
}

export default nextConfig;
