"""Recycle generated video artifacts without a permanent-delete fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


RECYCLE_TOOL = Path(r"E:\.agents\tools\Move-TaskItemToRecycleBin.ps1")


def recycle_generated(path: str | Path, allowed_root: str | Path) -> None:
    target = Path(path).absolute()
    root = Path(allowed_root).absolute()
    if not target.exists():
        return
    if target.is_symlink() or not target.is_relative_to(root) or target == root:
        raise ValueError(f"Generated cleanup target is outside its owner directory: {target}")
    if os.name != "nt":
        from send2trash import send2trash

        send2trash(str(target))
        return
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(RECYCLE_TOOL),
         "-LiteralPath", str(target), "-AllowedRoot", str(root), "-Json"],
        capture_output=True, text=True, timeout=90,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        raise OSError(f"Recycle failed for {target}: {result.stderr.strip()}")
    try:
        receipt = json.loads(result.stdout)
    except ValueError as error:
        raise OSError(f"Recycle receipt missing for {target}") from error
    if receipt.get("status") != "recycled" or target.exists():
        raise OSError(f"Recycle not verified for {target}: {result.stdout.strip()}")
