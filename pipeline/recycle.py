"""Recycle generated video artifacts without a permanent-delete fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


# Compatibility for the existing local installation; other machines configure
# their already trusted helper explicitly, never download or discover a script.
RECYCLE_TOOL = Path(r"E:\.agents\tools\Move-TaskItemToRecycleBin.ps1")


def _recycle_windows(target: Path, root: Path) -> None:
    configured = os.environ.get("VIDEO_RECYCLE_TOOL")
    tool = Path(configured) if configured is not None else RECYCLE_TOOL
    if not tool.is_absolute() or not tool.is_file():
        raise OSError(
            "Windows recycling requires an existing trusted helper; set "
            "VIDEO_RECYCLE_TOOL to its absolute .ps1 path"
        )
    try:
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(tool),
             "-LiteralPath", str(target), "-AllowedRoot", str(root), "-Json"],
            capture_output=True, text=True, timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        # The helper may already have acted. Report uncertainty, never retry.
        raise OSError(f"Recycle timed out for {target}; verify its state") from error
    if result.returncode != 0:
        raise OSError(f"Recycle failed for {target}: {result.stderr.strip()}")
    try:
        receipt = json.loads(result.stdout)
    except ValueError as error:
        raise OSError(f"Recycle receipt missing for {target}") from error
    if not isinstance(receipt, dict) or receipt.get("status") != "recycled":
        raise OSError(f"Recycle not verified for {target}: {result.stdout.strip()}")


def recycle_generated(path: str | Path, allowed_root: str | Path) -> None:
    target = Path(path)
    if target.is_symlink():
        raise ValueError(f"Generated cleanup target is outside its owner directory: {target}")
    target = target.resolve()
    root = Path(allowed_root).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError(f"Generated cleanup target is outside its owner directory: {target}")
    if not target.exists():
        return
    if os.name == "nt":
        _recycle_windows(target, root)
    else:
        from send2trash import send2trash

        send2trash(str(target))
    if target.exists():
        raise OSError(f"Recycle not verified for {target}: target still exists")
