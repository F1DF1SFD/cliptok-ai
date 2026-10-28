#!/usr/bin/env bash
# Build the downloadable, double-clickable ClipTok AI app.
#
# Produces dist/ClipTokAI-<version>-macOS-<arch>.zip and/or
# dist/ClipTokAI-<version>-windows-x64.zip containing everything a friend needs:
# the Next.js server, a bundled Node runtime, the Python backend, and a launcher
# that installs the Python side on first run.
#
# Usage: ./scripts/package.sh [--target=macos|windows|all] [--skip-build]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

NODE_VERSION="${CLIPTOK_NODE_VERSION:-v24.22.1}"
DIST_DIR="${CLIPTOK_DIST:-$ROOT/dist}"
BUILD_CACHE="$ROOT/build/cache"
STAGE_ROOT="$ROOT/build/package"
APP_NAME="ClipTok AI"
SKIP_BUILD=0
TARGET="macos"

for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=1 ;;
    --target=*) TARGET="${arg#*=}" ;;
    -h | --help)
      sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)" >&2
      exit 1
      ;;
  esac
done

case "$TARGET" in
  macos | windows | all) ;;
  *) echo "--target must be macos, windows or all" >&2 && exit 1 ;;
esac

if [[ ! -d frontend/node_modules ]]; then
  echo "Frontend dependencies are missing. Run ./scripts/setup.sh first." >&2
  exit 1
fi

ARCH="$(uname -m)"
VERSION="$(python3 -c "import json;print(json.load(open('frontend/package.json'))['version'])")"
mkdir -p "$BUILD_CACHE" "$DIST_DIR"

# --------------------------------------------------------------- 1. Build ----
if [[ "$SKIP_BUILD" == "0" ]]; then
  echo "==> Building the studio"
  # Rewrites are baked into the build, so every packaged app talks to its own
  # API on 127.0.0.1:8000. The output is platform independent (pure JS), so one
  # build serves both the macOS and Windows packages.
  (cd frontend && CLIPTOK_API_ORIGIN="http://127.0.0.1:8000" npm run build >/dev/null)
fi
[[ -d frontend/.next/standalone ]] || {
  echo "Standalone build missing. Is output: \"standalone\" set in next.config.mjs?" >&2
  exit 1
}

# --------------------------------------------------------- 2. Node runtime ----
# $1 = node dist arch (darwin-arm64, darwin-x64, win-x64)
fetch_node() {
  local node_arch="$1" archive
  if [[ "$node_arch" == win-* ]]; then
    archive="node-${NODE_VERSION}-${node_arch}.zip"
  else
    archive="node-${NODE_VERSION}-${node_arch}.tar.gz"
  fi
  if [[ ! -f "$BUILD_CACHE/$archive" ]]; then
    echo "==> Downloading Node ${NODE_VERSION} (${node_arch})"
    curl -fsSL --retry 3 -o "$BUILD_CACHE/$archive" \
      "https://nodejs.org/dist/${NODE_VERSION}/${archive}"
  fi
  if [[ ! -d "$BUILD_CACHE/node-${NODE_VERSION}-${node_arch}" ]]; then
    if [[ "$archive" == *.zip ]]; then
      (cd "$BUILD_CACHE" && unzip -qo "$archive")
    else
      tar -xzf "$BUILD_CACHE/$archive" -C "$BUILD_CACHE"
    fi
  fi
}

# $1 = staging dir
stage_common() {
  local stage="$1"
  mkdir -p "$stage/app/backend"
  rsync -a --exclude "__pycache__" --exclude "*.pyc" backend/app "$stage/app/backend/"
  cp backend/requirements.txt backend/requirements-bundle.txt "$stage/app/backend/"

  # Next standalone server, static assets and public files.
  rsync -a frontend/.next/standalone/ "$stage/app/web/"
  mkdir -p "$stage/app/web/.next"
  rsync -a frontend/.next/static "$stage/app/web/.next/"
  if [[ -d frontend/public ]]; then
    rsync -a frontend/public/ "$stage/app/web/public/"
  fi
  rm -rf "$stage/app/web/.next/cache"
}

# CRLF so cmd.exe is happy with the .bat.
crlf() {
  python3 - "$1" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
path.write_bytes(data)
PY
}

package_macos() {
  local node_arch stage zip
  case "$ARCH" in
    arm64) node_arch="darwin-arm64" ;;
    x86_64) node_arch="darwin-x64" ;;
    *) echo "Unsupported macOS architecture: $ARCH" >&2 && return 1 ;;
  esac
  stage="$STAGE_ROOT/macos/$APP_NAME"
  zip="$DIST_DIR/ClipTokAI-${VERSION}-macOS-${ARCH}.zip"

  echo "==> Assembling macOS app"
  rm -rf "$STAGE_ROOT/macos"
  mkdir -p "$stage/runtime"
  stage_common "$stage"

  fetch_node "$node_arch"
  cp "$BUILD_CACHE/node-${NODE_VERSION}-${node_arch}/bin/node" "$stage/runtime/node"
  chmod +x "$stage/runtime/node"
  cp "$BUILD_CACHE/node-${NODE_VERSION}-${node_arch}/LICENSE" "$stage/runtime/NODE-LICENSE" 2>/dev/null || true

  cp scripts/launcher.command "$stage/$APP_NAME.command"
  cp scripts/package-readme.txt "$stage/README.txt"
  chmod +x "$stage/$APP_NAME.command"
  printf "ClipTok AI %s\nBuilt %s for macOS %s\n" "$VERSION" "$(date -u +%Y-%m-%d)" "$ARCH" \
    >"$stage/VERSION.txt"

  echo "==> Zipping macOS"
  rm -f "$zip"
  (cd "$STAGE_ROOT/macos" && zip -qry "$zip" "$APP_NAME")
  echo "  $zip  ($(du -h "$zip" | cut -f1 | tr -d ' '))"
}

package_windows() {
  local stage zip
  stage="$STAGE_ROOT/windows/$APP_NAME"
  zip="$DIST_DIR/ClipTokAI-${VERSION}-windows-x64.zip"

  echo "==> Assembling Windows app"
  rm -rf "$STAGE_ROOT/windows"
  mkdir -p "$stage/runtime"
  stage_common "$stage"

  fetch_node "win-x64"
  cp "$BUILD_CACHE/node-${NODE_VERSION}-win-x64/node.exe" "$stage/runtime/node.exe"
  cp "$BUILD_CACHE/node-${NODE_VERSION}-win-x64/LICENSE" "$stage/runtime/NODE-LICENSE" 2>/dev/null || true

  cp "scripts/ClipTok AI.bat" "$stage/$APP_NAME.bat"
  cp scripts/launcher.py "$stage/launcher.py"
  cp scripts/package-readme-windows.txt "$stage/README.txt"
  crlf "$stage/$APP_NAME.bat"
  printf "ClipTok AI %s\r\nBuilt %s for Windows x64\r\n" "$VERSION" "$(date -u +%Y-%m-%d)" \
    >"$stage/VERSION.txt"

  echo "==> Zipping Windows"
  rm -f "$zip"
  (cd "$STAGE_ROOT/windows" && zip -qry "$zip" "$APP_NAME")
  echo "  $zip  ($(du -h "$zip" | cut -f1 | tr -d ' '))"
}

case "$TARGET" in
  macos) package_macos ;;
  windows) package_windows ;;
  all)
    package_macos
    package_windows
    ;;
esac

echo ""
echo "  Send the zip. Recipients double-click the launcher inside it."
echo ""
