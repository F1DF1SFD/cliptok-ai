/**
 * Static asset worker for the ClipTok AI demo site.
 *
 * The demo is a Next.js static export (frontend/out): all routes are pre-built
 * HTML, and the sample media lives under /demo. There is no API and no
 * rendering — this worker only serves the exported files.
 */
export default {
  async fetch(request, env) {
    return env.ASSETS.fetch(request);
  },
};
