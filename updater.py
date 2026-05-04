"""
updater.py — GitHub-based auto-updater for Screenshot Tool.

How it works
------------
1. On startup the editor calls check_for_update() in a background thread.
2. That function hits the GitHub Releases API and compares the latest tag
   against the local __version__ string.
3. If a newer version exists it returns an UpdateInfo object; the editor
   shows a banner with an "Install & Restart" button.
4. When the user clicks the button, download_and_apply() is called:
      a. Downloads the new .exe to a temp file.
      b. Writes a tiny .bat script that waits for this process to exit,
         overwrites the exe, then relaunches it.
      c. Launches the .bat and calls sys.exit() — Windows takes it from there.

Configuration
-------------
Set GITHUB_OWNER and GITHUB_REPO to match your GitHub account and repository.
The updater looks for a release asset named ScreenshotTool.zip.
"""

from __future__ import annotations

import os
import sys
import subprocess
import tempfile
import urllib.request
import urllib.error
import json
import logging
import zlib
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from version import __version__

logger = logging.getLogger(__name__)

GITHUB_OWNER = "JustinGlave"
GITHUB_REPO  = "Screenshot_Tool"

RELEASES_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
REQUEST_TIMEOUT = 8


@dataclass
class UpdateInfo:
    current_version: str
    latest_version:  str
    download_url:    str
    release_notes:   str


class UpdateError(RuntimeError):
    """Raised when an update cannot be checked, downloaded, or applied."""


class UpdateDownloadError(UpdateError):
    """Raised when the update archive cannot be downloaded completely."""


class UpdateValidationError(UpdateError):
    """Raised when a downloaded update archive is structurally invalid."""


def _parse_version(tag: str) -> tuple[int, ...]:
    cleaned = tag.lstrip("vV").strip()
    try:
        return tuple(int(p) for p in cleaned.split("."))
    except ValueError:
        return (0,)


def check_for_update() -> Optional[UpdateInfo]:
    """
    Query the GitHub Releases API.
    Returns UpdateInfo if a newer version is available, otherwise None.
    Safe to call from a background thread — never raises.
    """
    try:
        req = urllib.request.Request(
            RELEASES_API,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "ScreenshotTool"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())

        latest_tag = data.get("tag_name", "")
        if not latest_tag:
            return None

        if _parse_version(latest_tag) <= _parse_version(__version__):
            return None

        assets = data.get("assets", [])
        zip_asset = next(
            (a for a in assets if a.get("name", "").lower() == "screenshottool.zip"),
            None,
        )
        if zip_asset is None:
            zip_asset = next(
                (a for a in assets
                 if a.get("name", "").lower().endswith(".zip")
                 and "fullinstall" not in a.get("name", "").lower()),
                None,
            )
        if zip_asset is None:
            logger.warning("New release %s found but no .zip asset attached.", latest_tag)
            return None

        return UpdateInfo(
            current_version=__version__,
            latest_version=latest_tag.lstrip("vV"),
            download_url=zip_asset["browser_download_url"],
            release_notes=data.get("body", "").strip(),
        )

    except urllib.error.URLError as exc:
        logger.debug("Update check failed (network): %s", exc)
        return None
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("Update check failed: %s", exc)
        return None


def download_and_apply(info: UpdateInfo, progress_callback=None) -> None:
    """
    Download the new zip, extract it over the current exe, and restart.

    progress_callback(bytes_done, total_bytes) is called during download.
    Raises UpdateError on failure so the caller can show an error dialog.
    """
    if not getattr(sys, "frozen", False):
        raise UpdateError(
            "Update can only be applied to a compiled build.\n"
            "You are running from source — pull the latest code from GitHub instead."
        )

    current_exe = Path(sys.executable).resolve()

    tmp_fd, tmp_zip_str = tempfile.mkstemp(suffix=".zip")
    tmp_zip = Path(tmp_zip_str)
    tmp_fd_open = True

    try:
        req = urllib.request.Request(
            info.download_url,
            headers={"User-Agent": "ScreenshotTool"},
        )
        with os.fdopen(tmp_fd, "wb") as fh:
            tmp_fd_open = False
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                done  = 0
                chunk = 64 * 1024
                while True:
                    block = resp.read(chunk)
                    if not block:
                        break
                    fh.write(block)
                    done += len(block)
                    if progress_callback:
                        progress_callback(done, total)

        actual_size = tmp_zip.stat().st_size
        if total > 0 and actual_size < total:
            tmp_zip.unlink(missing_ok=True)
            raise UpdateDownloadError(
                f"Download incomplete: got {actual_size} of {total} bytes.\n"
                "Please try again or download manually from GitHub."
            )

    except UpdateDownloadError:
        if tmp_fd_open:
            os.close(tmp_fd)
        tmp_zip.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        if tmp_fd_open:
            os.close(tmp_fd)
        tmp_zip.unlink(missing_ok=True)
        raise UpdateDownloadError(f"Download failed: {exc}") from exc

    import zipfile
    try:
        with zipfile.ZipFile(tmp_zip) as zf:
            if "ScreenshotTool.exe" not in zf.namelist():
                raise UpdateValidationError(
                    "Update zip does not contain ScreenshotTool.exe.\n"
                    "Please try again or download manually from GitHub."
                )
            bad_file = zf.testzip()
            if bad_file:
                raise UpdateValidationError(
                    f"Update zip contains a corrupt file: {bad_file}\n"
                    "Please try again or download manually from GitHub."
                )
    except UpdateValidationError:
        tmp_zip.unlink(missing_ok=True)
        raise
    except (zipfile.BadZipFile, OSError, ValueError, zlib.error, NotImplementedError) as exc:
        tmp_zip.unlink(missing_ok=True)
        raise UpdateValidationError(
            "Downloaded update zip could not be validated.\n"
            "Please try again or download manually from GitHub."
        ) from exc

    pid      = os.getpid()
    exe_str  = str(current_exe)
    zip_str  = str(tmp_zip)

    # Write PowerShell script to a temp file to avoid quoting issues with spaces in paths
    ps_fd, ps_path_str = tempfile.mkstemp(suffix=".ps1")
    ps_path = Path(ps_path_str)
    ps_content = f"""
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipPath = '{zip_str.replace("'", "''")}'
$exePath = '{exe_str.replace("'", "''")}'
$zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
$entry = $zip.Entries | Where-Object {{ $_.Name -eq 'ScreenshotTool.exe' }} | Select-Object -First 1
if ($entry) {{
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $exePath, $true)
}}
$zip.Dispose()
Remove-Item $zipPath -ErrorAction SilentlyContinue
Start-Process $exePath
Remove-Item '{ps_path_str.replace("'", "''")}' -ErrorAction SilentlyContinue
"""
    with open(ps_fd, "w", encoding="utf-8") as fh:
        fh.write(ps_content)

    # Batch script waits for this process to exit, then runs the PowerShell
    bat_fd, bat_path_str = tempfile.mkstemp(suffix=".bat")
    bat_path = Path(bat_path_str)
    bat_content = f"""@echo off
:wait
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait
)
powershell -ExecutionPolicy Bypass -File "{ps_path_str}"
del "%~f0"
"""
    with open(bat_fd, "w") as fh:
        fh.write(bat_content)

    subprocess.Popen(
        ["cmd.exe", "/c", str(bat_path)],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )
    os._exit(0)  # hard exit — kills all threads so the bat script can replace the exe
