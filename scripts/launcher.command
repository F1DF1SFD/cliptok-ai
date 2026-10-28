#!/usr/bin/env bash
# ClipTok AI — double-click to start.
#
# First run installs its own Python environment (~1–3 minutes, needs internet).
# After that it starts in a few seconds. Your projects live in ~/.cliptok-ai/data.
set -uo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="${CLIPTOK_HOME:-$HOME/.cliptok-ai}"
VENV="$STATE_DIR/venv"
DATA="$STATE_DIR/data"
WEB_PORT="${CLIPTOK_PORT:-3000}"
API_PORT=8000 # fixed: the web app's build proxies /api to this port
BACKEND="$APP_DIR/app/backend"
WEB="$APP_DIR/app/web"
REQUIREMENTS="$BACKEND/requirements-bundle.txt"

BOLD="\033[1m"; DIM="\033[2m"; PURPLE="\033[38;5;141m"; RESET="\033[0m"

say() { printf "%b\n" "$*"; }
step() { printf "\n%b==> %s%b\n" "$PURPLE" "$*" "$RESET"; }
die() {
  printf "\n%b%s%b\n\n" "\033[31m" "$*" "$RESET" >&2
  printf "Press Enter to close." >&2
  read -r _ || true
  exit 1
}

printf "\n%b     ClipTok AI%b\n" "$PURPLE" "$RESET"
say "${DIM}     Twitch clips → captioned vertical shorts${RESET}"

[[ -d "$BACKEND" ]] || die "The app folder is incomplete (missing app/backend)."
mkdir -p "$STATE_DIR" "$DATA"

# ---------------------------------------------------------------- 1. Python --
step "Checking Python"
PY=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
    "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$(command -v "$candidate")"
    break
  fi
done

if [[ -z "$PY" ]]; then
  say "Python 3.10 or newer is required and wasn't found."
  if command -v brew >/dev/null 2>&1; then
    printf "Install it now with Homebrew? [y/N] "
    read -r answer
    if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
      brew install python@3.12 || die "Homebrew couldn't install Python."
      PY="$(command -v python3.12 || command -v python3 || true)"
    fi
  fi
  if [[ -z "$PY" ]]; then
    open "https://www.python.org/downloads/macos/" >/dev/null 2>&1 || true
    die "Install Python 3.10+ from python.org, then double-click ClipTok AI again."
  fi
fi
say "  ${PY}"

# ------------------------------------------------------------- 2. Venv/deps --
step "Preparing the engine"
if [[ ! -x "$VENV/bin/python" ]]; then
  say "  Creating a private Python environment in $STATE_DIR"
  "$PY" -m venv "$VENV" || die "Couldn't create the Python environment."
fi

STAMP="$STATE_DIR/.requirements-$(shasum "$REQUIREMENTS" | cut -c1-12)"
if [[ ! -f "$STAMP" ]]; then
  say "  Installing video + AI libraries (only happens once, ~2 min)"
  "$VENV/bin/python" -m pip install --quiet --upgrade pip setuptools wheel >/dev/null 2>&1 || true
  if ! "$VENV/bin/python" -m pip install --quiet -r "$REQUIREMENTS"; then
    die "Installing the libraries failed. Check your internet connection and try again."
  fi
  touch "$STAMP"
fi

step "Locating ffmpeg, ffprobe and yt-dlp"
# static-ffmpeg prints download chatter on first use, so the paths are emitted
# on a tagged last line and everything else is discarded.
BINARIES="$("$VENV/bin/python" - <<'PY' 2>/dev/null | grep '^##BINS##' | tail -n 1 | sed 's/^##BINS##//'
import contextlib
import io
import shutil

with contextlib.redirect_stdout(io.StringIO()):
    try:
        import static_ffmpeg

        static_ffmpeg.add_paths()
    except Exception:
        pass

print("##BINS##" + "\t".join(shutil.which(name) or "" for name in ("ffmpeg", "ffprobe", "yt-dlp")))
PY
)" || true

IFS=$'\t' read -r FFMPEG_BIN FFPROBE_BIN YTDLP_BIN <<<"${BINARIES:-}"
# Prefer the copy installed inside this app, not whatever Python happens to be on PATH.
[[ -x "$VENV/bin/yt-dlp" ]] && YTDLP_BIN="$VENV/bin/yt-dlp"
[[ -n "${FFMPEG_BIN:-}" && -n "${FFPROBE_BIN:-}" ]] || die \
  "ffmpeg is missing. Install it with 'brew install ffmpeg' and open ClipTok AI again."
say "  ffmpeg   ${FFMPEG_BIN}"
say "  yt-dlp   ${YTDLP_BIN:-not available (Twitch import disabled)}"

# ------------------------------------------------------------- 3. Ports ------
step "Starting the studio"
if curl -fsS -o /dev/null "http://127.0.0.1:${API_PORT}/api/health" 2>/dev/null; then
  die "ClipTok AI is already running in another window. Close it first (Ctrl+C there)."
fi

# Port 3000 is popular; walk forward until something is free.
BASE_PORT="$WEB_PORT"
for offset in $(seq 0 20); do
  WEB_PORT=$((BASE_PORT + offset))
  if ! curl -fsS -o /dev/null "http://127.0.0.1:${WEB_PORT}" 2>/dev/null; then break; fi
done
[[ "$WEB_PORT" != "$BASE_PORT" ]] && say "  port ${BASE_PORT} was busy, using ${WEB_PORT}"

NODE_BIN="$APP_DIR/runtime/node"
if [[ ! -x "$NODE_BIN" ]]; then
  NODE_BIN="$(command -v node || true)"
fi
[[ -n "$NODE_BIN" && -x "$NODE_BIN" ]] || die "The app's web runtime is missing (runtime/node)."

API_PID=""
WEB_PID=""
cleanup() {
  [[ -n "$WEB_PID" ]] && kill "$WEB_PID" 2>/dev/null || true
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

CLIPTOK_DATA_DIR="$DATA" \
  CLIPTOK_FFMPEG="$FFMPEG_BIN" \
  CLIPTOK_FFPROBE="$FFPROBE_BIN" \
  CLIPTOK_YTDLP="${YTDLP_BIN:-yt-dlp}" \
  "$VENV/bin/uvicorn" app.main:app \
  --app-dir "$BACKEND" --host 127.0.0.1 --port "$API_PORT" \
  >"$STATE_DIR/api.log" 2>&1 &
API_PID=$!

PORT="$WEB_PORT" HOSTNAME=127.0.0.1 NODE_ENV=production \
  "$NODE_BIN" "$WEB/server.js" >"$STATE_DIR/web.log" 2>&1 &
WEB_PID=$!

READY=""
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${WEB_PORT}/api/health" 2>/dev/null; then
    READY="yes"
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then break; fi
  sleep 1
done

if [[ -z "$READY" ]]; then
  say ""
  say "The studio didn't come up. Last lines from the logs:"
  tail -12 "$STATE_DIR/api.log" 2>/dev/null | sed 's/^/  api: /'
  tail -12 "$STATE_DIR/web.log" 2>/dev/null | sed 's/^/  web: /'
  die "Something went wrong starting ClipTok AI."
fi

open "http://127.0.0.1:${WEB_PORT}" >/dev/null 2>&1 || true
say ""
say "  ${BOLD}ClipTok AI is running${RESET}  http://127.0.0.1:${WEB_PORT}"
say "  ${DIM}Projects: $DATA${RESET}"
say "  ${DIM}Keep this window open while you edit. Ctrl+C quits.${RESET}"
say ""

while kill -0 "$WEB_PID" 2>/dev/null && kill -0 "$API_PID" 2>/dev/null; do
  sleep 2
done
