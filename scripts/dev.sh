#!/usr/bin/env bash
# Run the ClipTok AI API and the Next.js studio together.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
WHISPER_MODEL="${CLIPTOK_WHISPER_MODEL:-base}"
# The studio calls its own origin; Next proxies /api to the API below. Keeping the
# proxy means the same page works on localhost, a LAN address or a tunnel.
export CLIPTOK_API_ORIGIN="${CLIPTOK_API_ORIGIN:-http://127.0.0.1:${API_PORT}}"

if [[ ! -x backend/.venv/bin/uvicorn ]]; then
  echo "Backend dependencies are missing. Run ./scripts/setup.sh first." >&2
  exit 1
fi
if [[ ! -d frontend/node_modules ]]; then
  echo "Frontend dependencies are missing. Run ./scripts/setup.sh first." >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required but was not found on PATH." >&2
  exit 1
fi

API_PID=""
WEB_PID=""

cleanup() {
  if [[ -n "$API_PID" ]]; then kill "$API_PID" 2>/dev/null || true; fi
  if [[ -n "$WEB_PID" ]]; then kill "$WEB_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

echo "==> API      http://127.0.0.1:${API_PORT}  (Whisper: ${WHISPER_MODEL})"
CLIPTOK_WHISPER_MODEL="$WHISPER_MODEL" \
  backend/.venv/bin/uvicorn app.main:app \
  --app-dir backend \
  --host 127.0.0.1 \
  --port "$API_PORT" \
  --reload &
API_PID=$!

echo "==> Studio   http://localhost:${WEB_PORT}"
(
  cd frontend
  npm run dev -- -p "$WEB_PORT"
) &
WEB_PID=$!

# Stay in the foreground until either process exits, then clean both up.
while kill -0 "$API_PID" 2>/dev/null && kill -0 "$WEB_PID" 2>/dev/null; do
  sleep 1
done
