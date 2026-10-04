"""Discover original submissions without writing a manifest into their folders."""
from pathlib import Path
from .common import sha256


def discover(folder):
    root = Path(folder).resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    webpages, videos, files = [], [], []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Submission is not self-contained: " + str(path))
        item = {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
        files.append(item)
        if path.suffix.lower() in (".html", ".htm"):
            webpages.append(item["path"])
        elif path.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"):
            videos.append(item["path"])
    return {"schema": "webfilm.input.v1", "folder": str(root), "webpages": webpages, "videos": videos,
            "files": files, "selection_required": len(webpages) + len(videos) != 1,
            "note": "Original files are kept unchanged. Select an entry explicitly when more than one page/video exists. A model-exported video is accepted as a finished output; its code/media provenance is a separate declaration."}


def choose_page(folder, entry=None):
    result = discover(folder)
    if entry is None:
        if len(result["webpages"]) != 1:
            raise ValueError("Select --entry from webpage candidates: " + ", ".join(result["webpages"]))
        entry = result["webpages"][0]
    if entry not in result["webpages"]:
        raise ValueError("Selected page is not in the original submission")
    return Path(folder).resolve(), entry, result
