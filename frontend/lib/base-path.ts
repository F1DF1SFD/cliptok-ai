/**
 * Hosting under a sub-path (GitHub Pages project sites serve at
 * `https://user.github.io/<repo>/`). Next prefixes `_next/` assets and `Link`
 * hrefs itself; raw URLs we build by hand (sample media, share links) need this.
 *
 * Empty by default, so the desktop app and root-hosted demos are untouched.
 * `GITHUB_PAGES` in .github/workflows/pages.yml sets it from the repo name.
 */
export const BASE_PATH = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/+$/, "");

/** Prefix a root-relative path. Absolute and data/blob URLs pass through. */
export function assetPath(path: string): string {
  if (!path || !BASE_PATH) return path;
  if (/^(?:[a-z]+:)?\/\//i.test(path) || path.startsWith("data:") || path.startsWith("blob:")) {
    return path;
  }
  return `${BASE_PATH}${path.startsWith("/") ? path : `/${path}`}`;
}
