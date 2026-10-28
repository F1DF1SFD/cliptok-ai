#!/usr/bin/env bash
# Install ClipTok AI dependencies (backend venv + frontend node_modules).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON="$(command -v "$candidate")"
      break
    fi
  done
fi

if [[ -z "$PYTHON" ]]; then
  echo "Python 3.10+ is required." >&2
  exit 1
fi

for bin in ffmpeg ffprobe yt-dlp; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "warning: '$bin' was not found on PATH. Install it (brew install ffmpeg yt-dlp) before rendering." >&2
  fi
done

if [[ ! -d backend/.venv ]]; then
  echo "==> Creating Python virtualenv with $PYTHON"
  "$PYTHON" -m venv backend/.venv
fi

echo "==> Installing backend requirements"
backend/.venv/bin/python -m pip install --quiet --upgrade pip
backend/.venv/bin/pip install --quiet -r backend/requirements.txt

echo "==> Installing frontend dependencies"
(cd frontend && npm install --no-audit --no-fund)

if [[ ! -f frontend/.env.local ]]; then
  printf 'NEXT_PUBLIC_API_URL=http://127.0.0.1:8000\n' > frontend/.env.local
fi

echo
echo "Setup complete."
echo "  Start everything:  ./scripts/dev.sh"
echo "  Web app:           http://localhost:3000"
echo "  API docs:          http://127.0.0.1:8000/docs"
