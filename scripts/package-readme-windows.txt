ClipTok AI — Twitch clips into captioned vertical shorts (Windows)
==================================================================

What this is
------------
A complete studio for turning Twitch clips (or your own MP4s) into TikTok,
YouTube Shorts and Instagram Reels videos: Whisper captions, automatic 9:16
reframing that follows the action, facecam layouts, punch-in zooms, stickers,
music and one-click export at 1080x1920.

It runs on your PC. Nothing is uploaded to a website, and it works offline
after the first start.

Starting it
-----------
1. Unzip this folder somewhere permanent (e.g. C:\Users\you\Apps).
   Don't run it from inside the .zip or from a temporary folder.
2. Double-click "ClipTok AI.bat".
3. The first start sets up its own Python environment and downloads ffmpeg —
   expect a few minutes and an internet connection. After that, startup takes
   a few seconds.
4. Your browser opens at http://127.0.0.1:3000. Keep the black window open
   while you work; closing it (or Ctrl+C) stops the app.

Requires Python 3.10+ (the launcher tells you and opens the download page if
it's missing — tick "Add python.exe to PATH" during install).

If Windows SmartScreen warns about "ClipTok AI.bat", choose "More info" then
"Run anyway".

Using it
--------
- Paste a Twitch clip link, or drag an MP4 in.
- Open the project, then hit Transcribe (word-level captions) and Analyze
  (reframing + hype detection) if they haven't run yet.
- Tune captions, reframe, effects, audio and overlays in the right-hand panel.
- Export tab -> "Render final MP4" (1080x1920) -> download.
- Export tab -> "Create share link" makes a /s/... link you can send to anyone;
  "Turn off" revokes it.

First transcription downloads the Whisper model (~75 MB for "tiny",
~140 MB for "base") into %LOCALAPPDATA%\ClipTokAI\data\models.

Where things live
-----------------
- Projects, renders and models: %LOCALAPPDATA%\ClipTokAI\data
- Logs if something misbehaves: %LOCALAPPDATA%\ClipTokAI\api.log and web.log
- Delete %LOCALAPPDATA%\ClipTokAI to reset the app completely.

Notes
-----
- Rendering is CPU-heavy; a recent CPU with 8+ threads makes exports much
  faster. Close heavy games before exporting.
- Twitch import uses yt-dlp. If a clip stops working, update it with:
  %LOCALAPPDATA%\ClipTokAI\venv\Scripts\pip install -U yt-dlp
- The app listens on 127.0.0.1 only (nothing on your network can reach it).
  The share link feature exports a private link for a single clip.

Emoji stickers come from Twemoji (CC-BY 4.0).
