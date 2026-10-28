#!/usr/bin/env bash
# Share ClipTok AI with other people.
#
# Builds the studio, runs the API + web app on one origin, prints a link your
# friends can open (same Wi-Fi), and — if `cloudflared` is installed — a public
# https link that works anywhere. Share links for individual clips are created
# in the editor (Export tab -> Create share link).
#
# Usage: ./scripts/share.sh [--port=3000] [--no-build] [--tunnel|--no-tunnel]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
TUNNEL="${CLIPTOK_TUNNEL:-auto}" # auto | on | off
BUILD=1

usage() {
  sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD=0 ;;
    --tunnel) TUNNEL=on ;;
    --no-tunnel) TUNNEL=off ;;
    --port=*) WEB_PORT="${arg#*=}" ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)" >&2
      exit 1
      ;;
  esac
done

# Next bakes rewrites into the build manifest, so the API origin must be set for
# both the build and the server start.
export CLIPTOK_API_ORIGIN="http://127.0.0.1:${API_PORT}"

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
if curl -fsS -o /dev/null "http://127.0.0.1:${WEB_PORT}" 2>/dev/null; then
  echo "Port ${WEB_PORT} is already serving something. Pick another one: --port=3100" >&2
  exit 1
fi
if curl -fsS -o /dev/null "http://127.0.0.1:${API_PORT}/api/health" 2>/dev/null; then
  echo "Port ${API_PORT} already has a ClipTok API running." >&2
  echo "Stop it, or share on another pair: API_PORT=8010 ./scripts/share.sh --port=3100" >&2
  exit 1
fi

API_PID=""
WEB_PID=""
TUNNEL_PID=""
TUNNEL_LOG="$(mktemp -t cliptok-tunnel)"

cleanup() {
  for pid in "$WEB_PID" "$API_PID" "$TUNNEL_PID"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  rm -f "$TUNNEL_LOG"
}
trap cleanup EXIT INT TERM

wait_for() {
  local url="$1" label="$2"
  for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then return 0; fi
    sleep 1
  done
  echo "$label did not start within 60s." >&2
  return 1
}

if [[ "$BUILD" == "1" || ! -d frontend/.next ]]; then
  echo "==> Building the studio (first run takes a minute)"
  (cd frontend && npm run build)
fi

echo "==> API    http://127.0.0.1:${API_PORT}"
backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!
wait_for "http://127.0.0.1:${API_PORT}/api/health" "API"

echo "==> Studio on port ${WEB_PORT}"
(cd frontend && ./node_modules/.bin/next start -H 0.0.0.0 -p "$WEB_PORT") &
WEB_PID=$!
wait_for "http://127.0.0.1:${WEB_PORT}" "Studio"

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)"

echo ""
echo "  ClipTok AI is running"
echo "  Local     http://localhost:${WEB_PORT}"
if [[ -n "$LAN_IP" ]]; then
  echo "  Network   http://${LAN_IP}:${WEB_PORT}      (anyone on your Wi-Fi)"
fi

if [[ "$TUNNEL" != "off" ]]; then
  if command -v cloudflared >/dev/null 2>&1; then
    echo ""
    echo "==> Opening a public tunnel"
    cloudflared tunnel --url "http://127.0.0.1:${WEB_PORT}" --no-autoupdate >"$TUNNEL_LOG" 2>&1 &
    TUNNEL_PID=$!
    PUBLIC_URL=""
    for _ in $(seq 1 30); do
      PUBLIC_URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -1 || true)"
      [[ -n "$PUBLIC_URL" ]] && break
      sleep 1
    done
    if [[ -n "$PUBLIC_URL" ]]; then
      echo "  Public    ${PUBLIC_URL}      (send this to anyone)"
    else
      echo "  Public    tunnel did not come up — see ${TUNNEL_LOG}" >&2
      tail -5 "$TUNNEL_LOG" >&2 || true
    fi
  else
    echo ""
    echo "  Want a link that works outside your Wi-Fi?"
    echo "    brew install cloudflared && ./scripts/share.sh --tunnel"
  fi
fi

echo ""
echo "  Tip: open a clip -> Export tab -> \"Create share link\" to send a single finished video."
echo "  Press Ctrl+C to stop sharing."
echo ""

while kill -0 "$WEB_PID" 2>/dev/null && kill -0 "$API_PID" 2>/dev/null; do
  sleep 1
done
