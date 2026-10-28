@echo off
setlocal EnableExtensions
title ClipTok AI
cd /d "%~dp0"

echo.
echo      ClipTok AI
echo      Twitch clips into captioned vertical shorts
echo.

set "PY="

rem Prefer the Python launcher (py), then python on PATH. Need 3.10+.
py -3 -c "import sys;raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=py -3"

if not defined PY (
  python -c "import sys;raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
  if not errorlevel 1 set "PY=python"
)

if not defined PY (
  echo Python 3.10 or newer is required and wasn't found.
  echo.
  echo Installing it from the Microsoft Store or python.org will fix this.
  echo Opening the download page...
  start "" "https://www.python.org/downloads/windows/"
  echo.
  echo After installing, double-click "ClipTok AI" again.
  pause
  exit /b 1
)

%PY% "%~dp0launcher.py" %*
if errorlevel 1 (
  echo.
  echo ClipTok AI stopped with an error. The messages above explain why.
  pause
)
