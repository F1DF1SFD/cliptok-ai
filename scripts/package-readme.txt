ClipTok AI — Twitch clips into captioned vertical shorts
=========================================================

What this is
------------
A complete studio for turning Twitch clips (or your own MP4s) into TikTok,
YouTube Shorts and Instagram Reels videos: Whisper captions, automatic 9:16
reframing that follows the action, facecam layouts, punch-in zooms, stickers,
music and one-click export at 1080x1920.

It runs on your Mac. Nothing is uploaded to a website, and it works offline
after the first launch.

Starting it
-----------
1. Unzip this folder somewhere permanent (e.g. Applications or Movies).
   Don't run it from the Downloads folder or from inside the .zip.
2. Double-click "ClipTok AI.command".
3. The first launch sets up its own Python environment — expect 1–3 minutes
   and an internet connection. After that, startup takes a few seconds.
4. Your browser opens at http://127.0.0.1:3000. Keep the Terminal window open
   while you work; Ctrl+C (or closing it) stops the app.

If macOS says it "cannot be opened because the developer cannot be verified",
right-click "ClipTok AI.command" and choose Open, then confirm once.

Using it
--------
- Paste a Twitch clip link, or drag an MP4 in.
- Open the project, then hit Transcribe (word-level captions) and Analyze
  (reframing + hype detection) if they haven't run yet.
- Tune captions, reframe, effects, audio and overlays in the right-hand panel.
- Export tab → "Render final MP4" (1080x1920) → download.
- Export tab → "Create share link" makes a /s/... link you can send to anyone;
  "Turn off" revokes it.

First transcription downloads the Whisper model (~75 MB for "tiny",
~140 MB for "base") into ~/.cliptok-ai/data/models.

Requirements
------------
- macOS 12 or newer (Apple Silicon or Intel, matching this download).
- Python 3.10+ — a dialog will offer to install it via Homebrew if missing.
- ffmpeg: used from your system if present, otherwise a portable copy is
  downloaded automatically on first launch.
- Internet for the first launch (libraries + ffmpeg) and Twitch imports.

Where things live
-----------------
- Projects, renders and models: ~/.cliptok-ai/data
- Logs, if something misbehaves: ~/.cliptok-ai/api.log and web.log
- Delete ~/.cliptok-ai to reset the app completely.

Trouble?
--------
- "Port 3000 is already in use": quit the other app, or launch with
  CLIPTOK_PORT=3100 by running the .command from Terminal.
- Twitch import fails: clip may have expired, or Twitch changed something —
  updating yt-dlp fixes most cases:
  ~/.cliptok-ai/venv/bin/pip install -U yt-dlp
- Slow renders: transcoding on a laptop is CPU-heavy; close other apps.

Emoji stickers come from Twemoji (CC-BY 4.0).
