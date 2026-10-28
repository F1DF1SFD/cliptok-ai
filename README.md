# ClipTok AI

Turn Twitch clips into captioned, vertical short-form videos — locally.

ClipTok AI is a local-first studio for streamers: paste a Twitch clip (or drop an MP4), let
Whisper write word-perfect captions, let OpenCV track the action into a 9:16 frame, and render
TikTok / YouTube Shorts / Instagram Reels MP4s with punch-ins, stickers, sound effects and a
music bed.

Everything runs on your machine: FFmpeg, faster-whisper and OpenCV do the work and renders are
written into `backend/data/projects/<id>/renders/`. No third-party video API is involved.

## Feature tour

- **Twitch import** — paste a `clips.twitch.tv/...` or `twitch.tv/<channel>/clip/...` URL.
  yt-dlp resolves and downloads the clip, then metadata becomes the project title.
- **Uploads** — drag & drop MP4 / MOV / WebM / MKV (up to 512 MB, 10 minutes by default).
- **Whisper captions** — word-level timestamps from faster-whisper, grouped into 1–9 word
  caption lines with uppercase, pop-in animation, adjustable font, size, colours, outline,
  vertical position and three colour swatches.
- **Karaoke highlighting** — the spoken word switches to your accent colour and pops in while
  the rest of the line stays white with a hard black outline.
- **Auto reframe** — OpenCV tracks faces and motion, then FFmpeg pans a 9:16 crop along the
  action (`sendcmd` keyframes, 2 Hz, smoothed). Locked-center mode is available when tracking
  is not wanted.
- **Facecam split** — a stable corner facecam is detected and rendered as its own panel below
  the gameplay crop, so both stay visible.
- **TikTok-style edits** — snap punch-in zooms derived from the audio energy curve, optional
  motion blur on the zoom, white flash hits, saturation lift, fade-in.
- **Sound effects** — synthesized whoosh + thump placed at each punch-in (no third-party audio).
- **Audio** — original volume, uploaded music bed with looping, volume control and optional
  sidechain ducking under the voice.
- **Overlays** — meme text and a bundled 45-sticker emoji set, positioned and timed per clip.
- **Editor** — preview player with safe-zone guides, waveform timeline with draggable trim
  handles, caption overlay track, hype-moment markers, transcript panel with live word highlight.
- **Export presets** — TikTok 1080×1920 / 8 Mbps, YouTube Shorts 1080×1920 / 10 Mbps,
  Instagram Reels 1080×1920 / 8 Mbps, all H.264 + AAC with `+faststart`.
- **Share links** — publish a finished clip to a clean `/s/<slug>` watch page anyone can open
  (player + download, no studio access), and share the whole studio over your network or a
  tunnel with `./scripts/share.sh`.

## Tech stack

| Layer | Tools |
| --- | --- |
| Frontend | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, shadcn-style Radix UI components |
| Platforms | macOS 12+ and Windows 10/11 (Apple Silicon, Intel, x64) |
| Backend | Python 3.11, FastAPI, SQLite, background thread pool |
| Media | FFmpeg + ffprobe, yt-dlp |
| AI / CV | faster-whisper (Whisper), OpenCV (Haar face detection + motion tracking), NumPy |
| Captions | Pillow rasteriser, bundled Archivo Black font, system Arial/Impact/Segoe when available |

## Quickstart

Requirements: macOS or Linux, Python 3.10+, Node 20+, `ffmpeg`/`ffprobe` and `yt-dlp` on
`PATH`.

```bash
# 1. Install everything (creates backend/.venv and frontend/node_modules)
./scripts/setup.sh

# 2. Run API (:8000) + web app (:3000)
./scripts/dev.sh
# or: API_PORT=8000 WEB_PORT=3100 ./scripts/dev.sh
```

Manual alternative:

```bash
/opt/homebrew/bin/python3.11 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt

cd frontend && npm install
cd ../backend && .venv/bin/uvicorn app.main:app --port 8000 --reload
cd frontend && npm run dev        # separate terminal
```

Open <http://localhost:3000>, paste a clip, and the editor opens when the import finishes.

The first transcription downloads the Whisper model (≈140 MB for `base`, ≈75 MB for `tiny`)
into `backend/data/models/`. Set `CLIPTOK_WHISPER_MODEL=tiny` for fast drafts or `small`
for better accuracy.

## Send it to people

### Ship it as a downloadable app

```bash
./scripts/package.sh                     # macOS: dist/ClipTokAI-<version>-macOS-<arch>.zip (~55 MB)
./scripts/package.sh --target=windows    # Windows: dist/ClipTokAI-<version>-windows-x64.zip (~51 MB)
./scripts/package.sh --target=all        # both
```

Each zip is self-contained: the prebuilt Next.js server, a bundled Node runtime (so nobody
installs Node), the Python backend, and a launcher. Recipients unzip it and double-click
**ClipTok AI.command** (macOS) or **ClipTok AI.bat** (Windows); the launcher creates a private
Python venv, installs the libraries, downloads a portable ffmpeg/ffprobe when the machine has
none, starts the app and opens the browser. Projects live outside the app folder —
`~/.cliptok-ai/data` on macOS, `%LOCALAPPDATA%\ClipTokAI\data` on Windows — so their work
survives replacing the download.

What they need: macOS 12+ or Windows 10/11, Python 3.10+ (the macOS launcher offers the
Homebrew install; the Windows one opens the python.org page) and internet for the first launch.
No Node, no npm, no repo checkout.

Both builds run the same backend and the same standalone web build, so a project exported on one
machine opens on the other. Neither zip is code-signed: macOS may ask for right-click → Open, and
Windows SmartScreen wants "More info" → "Run anyway".

### Or send a link

The whole studio runs on your machine, so sharing means giving people a URL that points at it —
or sending a link to one finished clip.

**Share a single clip (recommended).** Open a project → **Export** tab → **Create share link**.
You get a private URL (`/s/<slug>`) with a clean watch page: vertical player, title, download
button. Recipients never see the studio and need no account. **Turn off** revokes the link
immediately.

**Let people use the studio.**

```bash
./scripts/share.sh                 # build + run on one URL, prints your LAN address
./scripts/share.sh --port=3100     # if 3000 is taken
./scripts/share.sh --tunnel        # also open a public https link (needs cloudflared)
```

`share.sh` builds the production frontend, runs the API and web app behind a single origin
(Next proxies `/api` to FastAPI), and prints:

```
  Local     http://localhost:3000
  Network   http://192.168.1.24:3000      (anyone on your Wi-Fi)
  Public    https://brave-lion-happy.trycloudflare.com   (send this to anyone)
```

For the public link, install the tunnel once with `brew install cloudflared`. Any tunnel works
too (ngrok, Tailscale Funnel) — just point it at the web port.

Because the API is proxied same-origin, previews, media streaming and share pages all work
behind that one URL; no CORS or `NEXT_PUBLIC_API_URL` tweaking is needed.

**Keep in mind:**

- Your Mac has to stay awake with `share.sh` running — renders happen on your hardware.
- Anyone who can open the studio URL can import, render **and delete** projects. Share
  individual clips if you only want people to watch; treat the studio link as "a friend on my
  couch", not as a public product.

### Or publish a read-only demo site

A static build with no backend, free to host anywhere: the landing page, library, editor
(timeline, captions, reframe, overlays, export panel, share) all work, and the two sample clips
are genuine renders from this pipeline.

```bash
make demo          # regenerate the samples, build frontend/out, then zip it into dist/
make demo-assets   # samples only (backend/.venv/bin/python scripts/make-demo-assets.py)
```

`make demo` leaves two things you can hand out: `frontend/out` (the site, ~2.8 MB of files) and
`dist/ClipTokAI-Demo-Site.zip` (~1.7 MB, `index.html` at the archive root) for hosts that want an
upload. To try the zip locally, unzip it anywhere and run `python3 -m http.server` in that folder.

`make demo-assets` draws a 10-second arena clip frame by frame, runs it through the real
OpenCV analysis and FFmpeg renderer (two variants: TikTok captions with punch-ins, and a Reels
facecam split), and writes `frontend/public/demo/` — about 1.4 MB of media plus a
`demo-data.json` that mirrors the API payloads exactly.

`frontend/out` is plain HTML, JS, CSS and MP4, so any static host works: Cloudflare Pages, Netlify,
GitHub Pages, an S3 bucket, `python3 -m http.server`. Preview it with `npx serve frontend/out`.
This repo's copy is deployed from [deploy/demo/manifest.json](deploy/demo/manifest.json) (a
one-line worker that serves the export) at
<https://site-c3c6705dadf94ff5ad9981499b991991.freebuff.page>.

#### Free hosting on GitHub Pages

[.github/workflows/pages.yml](.github/workflows/pages.yml) builds the demo on every push to `main`
and publishes it, so the live site always matches the repo — no local build, no upload.

1. Push this project to a GitHub repo (commands below).
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. Push to `main`, or run *Deploy demo site* from the Actions tab. The first run takes about two
   minutes; the site lands at `https://<user>.github.io/<repo>/`.

The workflow works out its own base path: a repo named `<user>.github.io` is served from the root,
anything else from `/<repo>/`. It passes that as `NEXT_PUBLIC_BASE_PATH`, which Next applies to
`_next/` assets and links while [lib/base-path.ts](frontend/lib/base-path.ts) applies it to the
sample media and share links. Reproduce the build locally with:

```bash
cd frontend
NEXT_PUBLIC_DEMO_MODE=1 NEXT_PUBLIC_BASE_PATH=/cliptok-demo npm run build
```

Getting the project onto GitHub in the first place:

```bash
git init -b main && git add -A && git commit -m "ClipTok AI"
git remote add origin git@github.com:<user>/<repo>.git   # or the https URL
git push -u origin main
```

What is different in a demo build (`NEXT_PUBLIC_DEMO_MODE=1`):

- `lib/api.ts` answers from `lib/demo.ts` instead of HTTP, so no server is needed.
- Uploads, import, transcription and rendering are refused with an explanation instead of
  failing — Whisper, OpenCV and FFmpeg need a machine you control.
- Settings edits are kept in `localStorage`, so the studio feels live without pretending to save.
- The share link points at a pre-rendered watch page (`/s/demo-clutch/`), not a real share record.

## Workflow

```
Twitch URL / MP4
      │
      ▼
Download + probe ──► project record (SQLite) + thumbnail
      │
      ▼
Whisper word timestamps ──► caption lines ──► Pillow overlay frames
      │
      ▼
OpenCV analysis: faces, facecam, motion trajectory, loudness peaks
      │
      ▼
FFmpeg pass 1: trim + tracked 9:16 crop (or gameplay/facecam stack)
FFmpeg pass 2: punch-in concat segments (snap zooms)
FFmpeg pass 3: overlay track + colour + flashes + music/SFX mix ──► MP4
```

The preview render is 540×960 for fast iteration; the final export is 1080×1920. Project times
are stored on the source timeline; the renderer offsets captions and overlays by the trim start.

## Project layout

```
backend/
  app/
    main.py              FastAPI app, CORS, capability health check
    routers/             projects, media (range streaming), catalog (fonts/stickers)
    services/
      analyze.py         OpenCV face/motion/facecam/energy analysis
      captions.py        word normalisation, line grouping, caption runs
      overlay.py         Pillow overlay rasteriser + concat script
      render.py          three-pass FFmpeg pipeline
      pipeline.py        project orchestration
      transcribe.py      faster-whisper wrapper
      twitch.py          yt-dlp import
      effects.py         synthesized SFX and placement
    assets/emoji/        bundled Twemoji stickers
    assets/fonts/        bundled caption font (used when no system font fits)
  tests/                 pytest unit + FFmpeg smoke tests
frontend/
  app/                   dashboard, editor and share routes
    s/[slug]/            page.app.tsx (server) and page.demo.tsx (static export);
                         next.config.mjs picks one via `pageExtensions`
  components/            app shell, dashboard, editor, UI primitives
  lib/                   API client, types, utils, demo mode
  public/demo/           sample media + demo-data.json (generated)
deploy/demo/             static-host worker + manifest for the demo site
scripts/                 setup.sh, dev.sh, share.sh, package.sh, make-demo-assets.py
```

## Configuration

Copy `.env.example` to `.env` (backend) or `frontend/.env.local` (web) as needed.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CLIPTOK_DATA_DIR` | `backend/data` | Projects, models, SQLite DB |
| `CLIPTOK_WHISPER_MODEL` | `base` | `tiny`, `base`, `small`, `medium`, `large-v3` |
| `CLIPTOK_WHISPER_DEVICE` | `auto` | `auto`, `cpu`, `cuda` |
| `CLIPTOK_WHISPER_COMPUTE` | `int8` | CTranslate2 compute type |
| `CLIPTOK_CORS_ORIGINS` | localhost:3000 | Comma-separated allowed origins |
| `CLIPTOK_MAX_CLIP_SECONDS` | `600` | Import/upload duration limit |
| `CLIPTOK_MAX_UPLOAD_MB` | `512` | Upload size limit |
| `CLIPTOK_FFMPEG` / `CLIPTOK_FFPROBE` / `CLIPTOK_YTDLP` | auto | Binary overrides |
| `NEXT_PUBLIC_API_URL` | *(same origin)* | API base for the web app; leave empty to use the built-in `/api` proxy |
| `NEXT_PUBLIC_DEMO_MODE` | *(off)* | `1` builds the read-only demo (static export, no backend) |
| `NEXT_PUBLIC_BASE_PATH` | *(root)* | Sub-path for static hosting, e.g. `/cliptok-demo` on GitHub Pages |
| `CLIPTOK_API_ORIGIN` | `http://127.0.0.1:8000` | Where Next proxies `/api` (read at build time) |
| `CLIPTOK_TUNNEL` | `auto` | `scripts/share.sh` public tunnel: `auto`, `on`, `off` |

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/health` | Engine capabilities, limits, presets, fonts |
| GET | `/api/projects` | List projects |
| POST | `/api/projects/import` | `{ "url": "https://clips.twitch.tv/..." }` |
| POST | `/api/projects/upload` | Multipart video upload |
| GET/PATCH/DELETE | `/api/projects/{id}` | Fetch / update settings / delete |
| POST | `/api/projects/{id}/transcribe` | Start Whisper job |
| POST | `/api/projects/{id}/analyze` | Re-run reframe analysis |
| POST | `/api/projects/{id}/render` | `{ "quality": "preview" \| "final" }` |
| POST/DELETE | `/api/projects/{id}/music` | Upload / remove a music bed |
| GET | `/api/jobs/{id}` | Job status + progress |
| GET | `/api/media/{id}/{path}` | Media streaming (HTTP range) |
| GET | `/api/stickers`, `/api/fonts` | Overlay assets |
| POST/DELETE | `/api/projects/{id}/share` | Publish / revoke a public clip link |
| GET | `/api/share/{slug}` | Public clip info for the watch page |
| GET | `/api/share/{slug}/video`, `/thumbnail` | Public video stream + poster |

## Tests

```bash
backend/.venv/bin/python -m pytest backend/tests -q
```

Unit tests cover caption grouping/normalisation, crop math, punch-in planning, sendcmd
generation, overlay timing and trim offsets. The smoke test builds a synthetic clip with
FFmpeg and renders a captioned vertical MP4 end-to-end.

## Notes & limitations

- **Caption rasteriser.** This repo targets minimal FFmpeg builds (for example static Homebrew
  builds without libass/freetype), so captions are drawn with Pillow and composited through the
  concat demuxer + `overlay` filter. If your FFmpeg does have libass, the overlay pipeline
  still works — no native dependency beyond FFmpeg itself.
- **Caption fonts.** The four caption faces resolve per platform: `Arial Black`, `Impact` and
  `Arial Bold` from `/System/Library/Fonts/Supplemental` on macOS; `ariblk.ttf`, `impact.ttf`,
  `arialbd.ttf` from `%WINDIR%\Fonts` on Windows, falling back to Segoe UI (`seguibl.ttf`,
  `segoeuib.ttf`) on stripped images. If none exist, captions use the bundled
  `backend/app/assets/fonts/ArchivoBlack-Regular.ttf` (SIL OFL), so rendering never depends on
  a machine having particular system fonts.
- **Face detection** uses OpenCV's Haar cascade: it needs a reasonably lit, frontal face and a
  stable facecam position. If no facecam is found, the split toggle stays disabled.
- **Twitch import** depends on yt-dlp and Twitch's public endpoints; clips can expire or be
  removed. The UI surfaces the yt-dlp error when that happens.
- **Local-first.** Project data and renders stay in `backend/data/`; nothing is uploaded to a
  third-party service. Sharing means pointing people at your running instance (or at a single
  clip's share link), so your machine has to stay awake while they watch or render.
- **Emoji stickers** are from [Twemoji](https://github.com/jdecked/twemoji) (CC-BY 4.0). See
  `backend/app/assets/emoji/README.md` for attribution.

## Troubleshooting

- **"API offline"** — start the backend (`./scripts/dev.sh` or uvicorn) and check
  `http://127.0.0.1:8000/api/health`.
- **"Missing engine: faster-whisper/OpenCV"** — reinstall backend requirements into
  `backend/.venv`.
- **First transcription is slow** — the Whisper model is downloading; subsequent runs use the
  cache in `backend/data/models`.
- **Import fails** — run `yt-dlp --version` and try the URL directly with
  `yt-dlp -J "<url>"`.
- **Render failed** — the job's error message includes the failing FFmpeg pass; the intermediate
  files remain in `backend/data/projects/<id>/work/`.
