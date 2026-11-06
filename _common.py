"""Shared helpers: locate ffmpeg/ffprobe and the workspace folder (inqueue/, InProgress/, Done/)."""
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


def find_tool(name: str) -> str:
    """$FFMPEG / $FFPROBE, then PATH, then the winget links folder on Windows."""
    env = os.environ.get(name.upper())
    if env:
        return env
    found = shutil.which(name)
    if found:
        return found
    links = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / f"{name}.exe"
    if links.exists():
        return str(links)
    raise SystemExit(f"{name} not found. Install ffmpeg (Windows: winget install Gyan.FFmpeg) "
                     f"or set the {name.upper()} environment variable to its path.")


FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")


def workspace(arg=None) -> Path:
    """--workspace, else $VIDKIT_WORKSPACE, else this repo's folder (inqueue/ etc. are git-ignored)."""
    return Path(arg or os.environ.get("VIDKIT_WORKSPACE") or HERE).resolve()
