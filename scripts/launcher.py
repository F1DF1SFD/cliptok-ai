#!/usr/bin/env python3
"""ClipTok AI supervisor.

Starts the studio from a packaged app folder: makes sure the Python
environment exists, installs the libraries on first run, resolves ffmpeg /
ffprobe / yt-dlp, then runs the FastAPI backend and the bundled Next.js server
and opens the browser.

Used by the Windows launcher (ClipTok AI.bat); runs on macOS and Linux too.
Requires only the standard library, so the system Python can run it before any
dependencies exist.

    python launcher.py [--port 3000] [--no-browser]
"""

from __future__ import annotations

import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
import webbrowser
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BACKEND = APP_DIR / "app" / "backend"
WEB = APP_DIR / "app" / "web"
RUNTIME = APP_DIR / "runtime"
REQUIREMENTS = BACKEND / "requirements-bundle.txt"
API_PORT = 8000  # fixed: the packaged web build proxies /api to this port
IS_WINDOWS = os.name == "nt"


def say(message: str = "") -> None:
    print(message, flush=True)


def step(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def fatal(message: str) -> "None":
    print(f"\n{message}\n", file=sys.stderr, flush=True)
    try:
        input("Press Enter to close.")
    except (EOFError, KeyboardInterrupt):
        pass
    sys.exit(1)


def state_dir() -> Path:
    override = os.environ.get("CLIPTOK_HOME")
    if override:
        return Path(override).expanduser()
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "ClipTokAI"


def venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.4)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def free_port(start: int) -> int:
    for candidate in range(start, start + 25):
        if not port_is_open(candidate):
            return candidate
    fatal(f"No free port between {start} and {start + 25}.")


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 400
    except (urllib.error.URLError, OSError, ValueError):
        return False


def tail(path: Path, lines: int = 12, prefix: str = "") -> None:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return
    for line in content:
        say(f"  {prefix}{line}")


def ensure_environment(state: Path) -> Path:
    root = state / "venv"
    python = venv_python(root)
    if not python.exists():
        say(f"  Creating a private Python environment in {root}")
        try:
            venv.EnvBuilder(with_pip=True, clear=False).create(root)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user below
            fatal(f"Couldn't create the Python environment: {exc}")
    if not python.exists():
        fatal("The Python environment is missing its interpreter. Delete " + str(state) + " and retry.")

    digest = hashlib.sha1(REQUIREMENTS.read_bytes()).hexdigest()[:12]
    stamp = state / f".requirements-{digest}-{sys.version_info.major}{sys.version_info.minor}"
    if not stamp.exists():
        say("  Installing video + AI libraries (only happens once, a few minutes)")
        install = subprocess.run(
            [str(python), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", str(REQUIREMENTS)],
            capture_output=True,
            text=True,
        )
        if install.returncode != 0:
            say(install.stdout[-2000:])
            say(install.stderr[-2000:])
            fatal("Installing the libraries failed. Check your internet connection and try again.")
        stamp.write_text("ok\n", encoding="utf-8")
    return python


PROBE = r"""
import contextlib, io, shutil, sys
with contextlib.redirect_stdout(io.StringIO()):
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except Exception:
        pass
print("##BINS##" + "\t".join(shutil.which(name) or "" for name in ("ffmpeg", "ffprobe", "yt-dlp")))
"""


def resolve_tools(python: Path, state: Path) -> tuple[str, str, str]:
    result = subprocess.run([str(python), "-c", PROBE], capture_output=True, text=True)
    line = next((ln for ln in reversed(result.stdout.splitlines()) if ln.startswith("##BINS##")), "")
    parts = line.removeprefix("##BINS##").split("\t") if line else ["", "", ""]
    while len(parts) < 3:
        parts.append("")

    local_ytdlp = venv_python(state.joinpath("venv")).parent / ("yt-dlp.exe" if IS_WINDOWS else "yt-dlp")
    if local_ytdlp.exists():
        parts[2] = str(local_ytdlp)

    ffmpeg, ffprobe, ytdlp = parts
    if not ffmpeg or not ffprobe:
        fatal(
            "ffmpeg is missing and couldn't be downloaded.\n"
            "Install it (Windows: 'winget install Gyan.FFmpeg', macOS: 'brew install ffmpeg') "
            "and start ClipTok AI again."
        )
    return ffmpeg, ffprobe, ytdlp


def node_binary() -> str:
    bundled = RUNTIME / ("node.exe" if IS_WINDOWS else "node")
    if bundled.exists() and os.access(bundled, os.X_OK):
        return str(bundled)
    found = shutil.which("node")
    if found:
        return found
    fatal("The app's web runtime is missing (runtime/node). Re-download ClipTok AI.")


def main() -> None:
    args = sys.argv[1:]
    preferred_port = 3000
    open_browser = True
    for index, arg in enumerate(args):
        if arg == "--port" and index + 1 < len(args):
            preferred_port = int(args[index + 1])
        elif arg.startswith("--port="):
            preferred_port = int(arg.split("=", 1)[1])
        elif arg == "--no-browser":
            open_browser = False

    say("\n     ClipTok AI")
    say("     Twitch clips into captioned vertical shorts")

    if not BACKEND.is_dir() or not WEB.is_dir():
        fatal("The app folder is incomplete. Unzip the whole download and try again.")
    if sys.version_info < (3, 10):
        fatal(f"Python 3.10 or newer is required (this is {sys.version.split()[0]}).")

    state = state_dir()
    state.mkdir(parents=True, exist_ok=True)
    data = state / "data"
    data.mkdir(parents=True, exist_ok=True)

    step("Preparing the engine")
    python = ensure_environment(state)

    step("Locating ffmpeg, ffprobe and yt-dlp")
    ffmpeg, ffprobe, ytdlp = resolve_tools(python, state)
    say(f"  ffmpeg   {ffmpeg}")
    say(f"  yt-dlp   {ytdlp or 'not available (Twitch import disabled)'}")

    step("Starting the studio")
    if http_ok(f"http://127.0.0.1:{API_PORT}/api/health"):
        fatal("ClipTok AI is already running in another window. Close it first.")

    port = free_port(preferred_port)
    if port != preferred_port:
        say(f"  port {preferred_port} was busy, using {port}")

    environment = os.environ.copy()
    environment.update(
        {
            "CLIPTOK_DATA_DIR": str(data),
            "CLIPTOK_FFMPEG": ffmpeg,
            "CLIPTOK_FFPROBE": ffprobe,
            "CLIPTOK_YTDLP": ytdlp or "yt-dlp",
            "PYTHONUNBUFFERED": "1",
            "PORT": str(port),
            "HOSTNAME": "127.0.0.1",
            "NODE_ENV": "production",
        }
    )

    creationflags = 0
    if IS_WINDOWS:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    api_log = (state / "api.log").open("w", encoding="utf-8")
    web_log = (state / "web.log").open("w", encoding="utf-8")

    api = subprocess.Popen(
        [str(python), "-m", "uvicorn", "app.main:app", "--app-dir", str(BACKEND),
         "--host", "127.0.0.1", "--port", str(API_PORT)],
        cwd=str(BACKEND),
        env=environment,
        stdout=api_log,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    web = subprocess.Popen(
        [node_binary(), str(WEB / "server.js")],
        cwd=str(WEB),
        env=environment,
        stdout=web_log,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )

    url = f"http://127.0.0.1:{port}"
    try:
        ready = False
        for _ in range(90):
            if api.poll() is not None:
                break
            if web.poll() is not None:
                break
            if http_ok(f"{url}/api/health"):
                ready = True
                break
            time.sleep(1)

        if not ready:
            say("\nThe studio didn't come up. Last lines from the logs:")
            tail(state / "api.log", prefix="api: ")
            tail(state / "web.log", prefix="web: ")
            fatal("Something went wrong starting ClipTok AI.")

        if open_browser:
            webbrowser.open(url)

        say("")
        say(f"  ClipTok AI is running  {url}")
        say(f"  Projects: {data}")
        say("  Keep this window open while you edit. Ctrl+C quits.")
        say("")

        while api.poll() is None and web.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        say("\nStopping ClipTok AI...")
    finally:
        for process in (web, api):
            if process.poll() is None:
                process.terminate()
        for process in (web, api):
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
        api_log.close()
        web_log.close()


if __name__ == "__main__":
    main()
