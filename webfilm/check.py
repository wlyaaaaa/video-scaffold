"""Inventory and practical contest-rule checks (not a provenance oracle)."""
from __future__ import annotations

from html.parser import HTMLParser
import math
from pathlib import Path
import re
from urllib.parse import urlparse, unquote

from .common import read_json, sha256

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mp3", ".wav", ".ogg", ".opus", ".m4a", ".aac", ".flac", ".aiff", ".wma"}
TEXT_EXTENSIONS = {".html", ".htm", ".js", ".mjs", ".css", ".svg", ".json"}


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Resource leaves the work folder: {relative}")
    return path


def load_work(folder, *, max_duration=120):
    root = Path(folder).resolve()
    config = read_json(root / "work.json")
    if config.get("schema") != 1:
        raise ValueError("work.json schema must be 1")
    duration = config.get("duration")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 0 < duration <= max_duration:
        raise ValueError(f"duration must be greater than zero and at most {max_duration} seconds")
    entry = config.get("entry", "index.html")
    if not isinstance(entry, str) or not inside(root, entry).is_file():
        raise ValueError("Entry page is missing or outside the work folder")
    if config.get("audio", "none") not in ("none", "generated"):
        raise ValueError("audio must be none or generated")
    seed = config.get("seed", 829)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xffffffff:
        raise ValueError("seed must be a 32-bit unsigned integer")
    return root, config


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.resources = []
        self.media = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("video", "audio"):
            self.media.append(tag)
        for key in ("src", "poster", "data", "xlink:href"):
            if attrs.get(key):
                self.resources.append(attrs[key])
        if tag in ("link", "image", "use", "script") and attrs.get("href"):
            self.resources.append(attrs["href"])
        if attrs.get("srcset"):
            self.resources.extend(item.strip().split()[0] for item in attrs["srcset"].split(",") if item.strip())


def media_magic(data):
    if data.startswith((b"ID3", b"OggS", b"fLaC", b"\x1a\x45\xdf\xa3")):
        return True
    if data[:4] == b"RIFF" and data[8:12] in (b"WAVE", b"AVI "):
        return True
    return data[4:8] == b"ftyp" or (len(data) > 1 and data[0] == 0xff and data[1] & 0xe0 == 0xe0)


def check_work(folder, *, max_duration=120, config=None):
    if config is None:
        root, config = load_work(folder, max_duration=max_duration)
    else:
        root = Path(folder).resolve()
        if not 0 < config["duration"] <= max_duration:
            raise ValueError("Capture duration exceeds its configured limit")
    errors, warnings, inventory = [], [], []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            errors.append(f"{relative}: symlink or external material is not self-contained")
            continue
        data = path.read_bytes()
        inventory.append({"path": relative, "bytes": len(data), "sha256": sha256(path)})
        if relative in config.get("accepted_exports", []):
            continue  # Finished model exports are inputs, not webpage media assets.
        if path.suffix.lower() in MEDIA_EXTENSIONS or media_magic(data[:32]):
            errors.append(f"{relative}: prerecorded audio/video file is forbidden")
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            errors.append(f"{relative}: source text is not UTF-8")
            continue
        links = []
        if path.suffix.lower() in (".html", ".htm", ".svg"):
            parser = Links()
            parser.feed(text)
            links += parser.resources
            if parser.media:
                errors.append(f"{relative}: audio/video elements are forbidden; use generated Web Audio")
        links += re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", text, re.I)
        links += re.findall(r"@import\s+['\"]([^'\"]+)", text, re.I)
        links += re.findall(r"(?:\bimport\s*(?:[^'\"]*?from\s*)?|\bimport\s*\()\s*['\"]([^'\"]+)['\"]", text)
        for uri in links:
            parsed = urlparse(uri)
            if uri.startswith("data:"):
                if re.match(r"data:(audio|video)/", uri, re.I):
                    errors.append(f"{relative}: embedded prerecorded media is forbidden")
                continue
            if uri.startswith("#"):
                continue
            if parsed.scheme or parsed.netloc:
                errors.append(f"{relative}: external resource: {uri[:160]}")
                continue
            local = (root / unquote(parsed.path.lstrip("/"))) if parsed.path.startswith("/") else path.parent / unquote(parsed.path)
            if not local.resolve().is_relative_to(root) or not local.is_file():
                errors.append(f"{relative}: missing or external local resource: {uri[:160]}")
        if re.search(r"\b(?:WebSocket|EventSource|RTCPeerConnection)\s*\(", text):
            errors.append(f"{relative}: network channel API is forbidden")
        if re.search(r"(?:fetch\s*\(|XMLHttpRequest|sendBeacon\s*\()", text):
            warnings.append(f"{relative}: request API found; runtime inspection must confirm local requests only")
        if re.search(r"data:(?:audio|video)/", text, re.I):
            errors.append(f"{relative}: embedded prerecorded media is forbidden")
    if not inventory:
        errors.append("Empty work folder")
    return {"schema": "webfilm.check.v1", "pass": not errors, "scope": "static",
            "title": config.get("title", "Untitled"), "duration": config["duration"],
            "errors": errors, "warnings": warnings, "files": inventory,
            "manual": ["Confirm the model did not use a video generation model or conceal prerecorded media; this cannot be proven from file scans."]}
