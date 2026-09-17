"""Bounded processes and atomic outputs shared by the video pipeline."""

from __future__ import annotations
import contextlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid


def positive(value, name="value", *, zero=False):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or (value < 0 if zero else value <= 0)
    ):
        raise ValueError(
            f"{name} must be a finite {'nonnegative' if zero else 'positive'} number"
        )
    return float(value)


@contextlib.contextmanager
def atomic_output(path):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    work = target.with_name(f".{target.stem}.work-{uuid.uuid4().hex}{target.suffix}")
    try:
        yield str(work)
        if not work.is_file() or work.stat().st_size == 0:
            raise RuntimeError(f"empty generated output: {target.name}")
        os.replace(work, target)
    finally:
        work.unlink(missing_ok=True)


def atomic_text(path, text):
    with atomic_output(path) as work:
        Path(work).write_text(text, encoding="utf-8", newline="\n")


def atomic_json(path, value):
    atomic_text(
        path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )


def run(command, *, timeout=120, **kwargs):
    options = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
        "check": True,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    options.update(kwargs)
    try:
        return subprocess.run(command, **options)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"{Path(command[0]).name} failed ({error.returncode}): {(error.stderr or '')[-3000:]}"
        ) from error


def concat_entry(path):
    value = Path(path).resolve().as_posix()
    if "\n" in value or "\r" in value:
        raise ValueError("newline in concat path")
    return "file '" + value.replace("'", "'\\''") + "'\n"


@contextlib.contextmanager
def project_lock(root):
    """OS file lock: automatically released on process exit, no stale PID guessing."""
    path = Path(root) / ".video-workflow.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+b") as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError(
                "another video workflow is writing this project"
            ) from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def publish_bundle(pairs):
    """Replace a small set of sibling artifacts, restoring old files on failure."""
    token = uuid.uuid4().hex
    backups = []
    installed = []
    try:
        for source, target in pairs:
            source, target = Path(source), Path(target)
            if not source.is_file() or source.stat().st_size == 0:
                raise RuntimeError(f"empty staged artifact: {source.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
        for source, target in pairs:
            target = Path(target)
            if target.exists():
                backup = target.with_name(f".{target.name}.previous-{token}")
                os.replace(target, backup)
                backups.append((backup, target))
            os.replace(source, target)
            installed.append(target)
    except BaseException:
        for target in reversed(installed):
            target.unlink(missing_ok=True)
        for backup, target in reversed(backups):
            os.replace(backup, target)
        raise
    else:
        for backup, target in backups:
            backup.unlink()


class _WindowsJob:
    """Kill only this worker's encoder if its owning process disappears."""

    def __init__(self, process):
        self.handle = None
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes as W

        class Basic(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64),
                ("job_time", ctypes.c_int64),
                ("flags", W.DWORD),
                ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t),
                ("active", W.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", W.DWORD),
                ("scheduling", W.DWORD),
            ]

        class IO(ctypes.Structure):
            _fields_ = [
                (n, ctypes.c_uint64) for n in ("ro", "wo", "oo", "rt", "wt", "ot")
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("basic", Basic),
                ("io", IO),
                ("process_limit", ctypes.c_size_t),
                ("job_limit", ctypes.c_size_t),
                ("process_peak", ctypes.c_size_t),
                ("job_peak", ctypes.c_size_t),
            ]

        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, W.LPCWSTR]
        k.CreateJobObjectW.restype = W.HANDLE
        k.SetInformationJobObject.argtypes = [
            W.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            W.DWORD,
        ]
        k.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]
        k.CloseHandle.argtypes = [W.HANDLE]
        h = k.CreateJobObjectW(None, None)
        limits = Extended()
        limits.basic.flags = 0x2000
        if (
            not h
            or not k.SetInformationJobObject(
                h, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            )
            or not k.AssignProcessToJobObject(h, W.HANDLE(int(process._handle)))
        ):
            code = ctypes.get_last_error()
            if h:
                k.CloseHandle(h)
            process.kill()
            process.wait()
            raise OSError(code, "encoder process supervision unavailable")
        self.handle = h
        self.kernel = k

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


@contextlib.contextmanager
def encoder_process(command, timeout):
    import threading

    with tempfile.TemporaryFile() as errors:
        kwargs = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.DEVNULL,
            "stderr": errors,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        process = subprocess.Popen(command, **kwargs)
        job = _WindowsJob(process)

        def expire():
            try:
                if process.poll() is None:
                    process.kill()
            except OSError:
                pass

        timer = threading.Timer(timeout, expire)
        timer.daemon = True
        timer.start()
        try:
            yield process, errors
        finally:
            timer.cancel()
            if process.stdin:
                with contextlib.suppress(OSError):
                    process.stdin.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            job.close()


def safe_print(*values, **kwargs):
    """Keep diagnostics usable with legacy Windows pipe encodings.

    CLI entrypoints request UTF-8. A library caller may still provide a cp1252
    stream; retain unrepresentable characters as escapes rather than failing
    the business operation or mutating the caller's global stream settings.
    """
    import builtins
    import sys

    stream = kwargs.get("file") or sys.stdout
    encoding = getattr(stream, "encoding", None)
    if encoding:

        def represent(value):
            return (
                str(value).encode(encoding, errors="backslashreplace").decode(encoding)
            )

        values = tuple(represent(value) for value in values)
        for key in ("sep", "end"):
            if kwargs.get(key) is not None:
                kwargs[key] = represent(kwargs[key])
    builtins.print(*values, **kwargs)
