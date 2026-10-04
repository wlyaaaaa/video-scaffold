"""Small shared helpers; machine adapters are optional and never committed."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def machine_profile():
    explicit = os.environ.get("WEBFILM_MACHINE")
    path = Path(explicit) if explicit else Path(__file__).resolve().parent.parent / ".video-machine.json"
    return read_json(path) if path.is_file() else {}


def tool(name):
    configured = os.environ.get("WEBFILM_" + name.upper())
    if configured:
        if not Path(configured).is_file():
            raise FileNotFoundError(f"Configured {name} is missing: {configured}")
        return configured
    folder = machine_profile().get("ffmpeg_directory") if name in ("ffmpeg", "ffprobe") else None
    if folder:
        candidate = Path(folder) / (name + (".exe" if os.name == "nt" else ""))
        if candidate.is_file():
            return str(candidate)
    resolved = shutil.which(name)
    if not resolved:
        raise FileNotFoundError(f"{name} is missing; install it or set WEBFILM_{name.upper()}")
    return resolved


def chrome_path():
    configured = os.environ.get("WEBFILM_CHROME")
    if configured:
        if not Path(configured).is_file():
            raise FileNotFoundError("Configured Chrome executable is missing")
        return str(Path(configured).resolve())
    candidates = []
    if os.name == "nt":
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                    candidates.append(winreg.QueryValue(key, None))
            except OSError:
                pass
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            if os.environ.get(variable):
                candidates.append(str(Path(os.environ[variable]) / "Google/Chrome/Application/chrome.exe"))
    else:
        candidates.extend(filter(None, (shutil.which("google-chrome"), shutil.which("google-chrome-stable"))))
        candidates.append("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    for candidate in candidates:
        if Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise FileNotFoundError("Google Chrome is missing; set WEBFILM_CHROME to its installed executable")


def run(args, timeout=1800, **kwargs):
    result = subprocess.run([str(arg) for arg in args], capture_output=True, creationflags=NO_WINDOW,
                            timeout=timeout, **kwargs)
    if result.returncode:
        stderr = result.stderr.decode("utf-8", "replace") if isinstance(result.stderr, bytes) else result.stderr
        raise RuntimeError(f"{Path(str(args[0])).name} failed ({result.returncode}): {stderr[-6000:]}")
    return result


def probe(path):
    return json.loads(run([tool("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", path]).stdout)


def recycle(path, allowed_root):
    path, root = Path(path).resolve(), Path(allowed_root).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Recycle target must be inside the task's temporary root")
    if not path.exists():
        return
    if os.name == "nt":
        helper = Path(os.environ.get("WEBFILM_RECYCLE_TOOL", r"E:\.agents\tools\Move-TaskItemToRecycleBin.ps1"))
        if not helper.is_file():
            raise RuntimeError(f"Trusted recycling helper is unavailable; temporary files retained at {path}")
        receipt = json.loads(run(["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", helper,
                                 "-LiteralPath", path, "-AllowedRoot", root, "-Json"], timeout=120).stdout)
        if receipt.get("status") != "recycled" or path.exists():
            raise RuntimeError(f"Recycling was not verified: {path}")
    else:
        from send2trash import send2trash
        send2trash(str(path))


@contextmanager
def temp_workspace(output_parent, prefix="webfilm-"):
    explicit = os.environ.get("WEBFILM_TEMP")
    root = Path(explicit) if explicit else Path(output_parent).resolve() / ".webfilm-tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=root))
    try:
        yield path
    finally:
        recycle(path, root)


def new_output(path):
    path = Path(path).resolve()
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite an existing result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
