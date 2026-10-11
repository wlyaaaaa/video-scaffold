"""Shared FIFO for pages render/stills and the compatible command wrapper.

Use ``with lease(label): ...`` or ``python -m pipeline.render_queue -- command``.
VIDEO_RENDER_SLOTS (2), VIDEO_RENDER_MIN_FREE_GB (14), VIDEO_RENDER_SLOT_DIR
remain configurable. An otherwise idle queue admits one job even below the
memory threshold. OS locks, rather than PID guesses, identify live owners.
"""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

SLOTS = int(os.environ.get("VIDEO_RENDER_SLOTS", "2"))
MIN_FREE_GB = float(os.environ.get("VIDEO_RENDER_MIN_FREE_GB", "14"))
_default_dir = (Path("E:/Cache/video-scaffold-render-slots")
                if os.name == "nt" and Path("E:/Cache").is_dir()
                else Path.home() / ".cache/video-scaffold/render-slots")
SLOT_DIR = os.environ.get("VIDEO_RENDER_SLOT_DIR", str(_default_dir))
POLL_SECONDS = 5
REPORT_SECONDS = 30
_INHERITED = "VIDEO_RENDER_QUEUE_LEASE"
_local = threading.local()
if SLOTS < 1 or not math.isfinite(MIN_FREE_GB) or MIN_FREE_GB < 0:
    raise ValueError("render slots must be positive and minimum free memory nonnegative")


def free_gb():
    """Available physical memory in GiB; unavailable measurements are conservative."""
    if os.name != "nt":
        try:
            with open("/proc/meminfo", encoding="ascii") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) / 1024**2
        except OSError:
            pass
        return 0.0

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total", "available", "page_total", "page_available",
             "virtual_total", "virtual_available", "extended")]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return 0.0
    return status.available / 1024**3


def auto_workers(available_gb=None):
    """Reserve the admission margin, then budget 3 GiB per worker and queue slot.

    This is a conservative starting estimate, not a hard memory limit. Keep the
    existing four-worker ceiling unless the caller explicitly overrides it.
    """
    override = os.environ.get("VIDEO_RENDER_WORKERS")
    if override is not None:
        workers = int(override)
        if workers < 1:
            raise ValueError("VIDEO_RENDER_WORKERS must be positive")
        _event("workers", workers=workers, selection="VIDEO_RENDER_WORKERS")
        return workers
    free = free_gb() if available_gb is None else available_gb
    workers = (max(1, min(4, int(max(0, free - MIN_FREE_GB) / (3 * SLOTS))))
               if math.isfinite(free) else 1)
    _event("workers", workers=workers, selection="memory", slots=SLOTS,
           free_gib=round(free, 3) if math.isfinite(free) else None,
           reserve_gib=MIN_FREE_GB, per_worker_gib=3)
    return workers


def _try_lock(handle):
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(handle):
    handle.seek(0)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _guard():
    root = Path(SLOT_DIR)
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".queue.lock").open("a+b") as handle:
        if handle.seek(0, 2) == 0:
            handle.write(b" ")
            handle.flush()
        while not _try_lock(handle):
            time.sleep(0.02)
        try:
            yield
        finally:
            _unlock(handle)


def _write(handle, record):
    # The first byte stays locked; readers only access the JSON after it.
    handle.seek(1)
    handle.write(json.dumps(record, ensure_ascii=False).encode("utf-8"))
    handle.truncate()
    handle.flush()


def _records():
    """Called under the registry lock; reclaim records whose OS lock is free."""
    records = []
    for path in sorted((Path(SLOT_DIR) / "queue").glob("*.ticket")):
        with path.open("r+b") as handle:
            stale = _try_lock(handle)
            if stale:
                _unlock(handle)
            else:
                handle.seek(1)
                records.append(json.loads(handle.read().decode("utf-8")))
        if stale:
            path.unlink()
            _event("reclaimed", ticket=path.name)
    return records


def _event(event, **fields):
    print(json.dumps({"source": "render_queue", "event": event,
                      "at": datetime.now(timezone.utc).isoformat(),
                      "pid": os.getpid(), **fields}, ensure_ascii=False), flush=True)


@contextmanager
def lease(label="render"):
    """Own one queue place; nested calls and the wrapper's child borrow it."""
    existing = getattr(_local, "record", None)
    if existing is not None and getattr(_local, "pid", None) == os.getpid():
        yield existing
        return
    handle = None
    path = None
    started = time.monotonic()
    try:
        with _guard():
            queue_dir = Path(SLOT_DIR) / "queue"
            queue_dir.mkdir(exist_ok=True)
            records = _records()
            inherited = os.environ.get(_INHERITED)
            record = next((r for r in records if r["state"] == "active"
                           and str((queue_dir / r["ticket"]).resolve()) == inherited), None)
            if record is None:
                # Increment beyond every live ticket even if wall time goes backwards.
                number = max([time.time_ns()] + [int(r["ticket"].split("-")[0]) + 1 for r in records])
                path = queue_dir / f"{number:020d}-{os.getpid()}.ticket"
                handle = path.open("x+b")
                handle.write(b" ")
                handle.flush()
                if not _try_lock(handle):
                    raise RuntimeError("cannot lock own queue ticket")
                record = {"ticket": path.name, "pid": os.getpid(), "label": str(label),
                          "state": "waiting", "queued_at": datetime.now(timezone.utc).isoformat()}
                _write(handle, record)
                _event("queued", **record, slots=SLOTS, queue_dir=str(queue_dir.resolve()))
        if handle is not None:
            last_report = float("-inf")
            while True:
                with _guard():
                    records = _records()
                    active = sum(r["state"] == "active" for r in records)
                    ahead = sum(r["state"] == "waiting" and r["ticket"] < record["ticket"] for r in records)
                    free = free_gb()
                    fields = {"ticket": record["ticket"], "label": str(label), "ahead": ahead,
                              "active": active, "slots": SLOTS, "free_gib": round(free, 3),
                              "min_free_gib": MIN_FREE_GB, "wait_seconds": round(time.monotonic() - started, 3)}
                    if ahead == 0 and active < SLOTS and (active == 0 or free >= MIN_FREE_GB):
                        record.update(state="active", admitted_at=datetime.now(timezone.utc).isoformat())
                        _write(handle, record)
                        _event("admitted", **{**fields, "active": active + 1})
                        break
                    if time.monotonic() - last_report >= REPORT_SECONDS:
                        _event("waiting", **fields)
                        last_report = time.monotonic()
                time.sleep(POLL_SECONDS)
        else:
            _event("borrowed", ticket=record["ticket"], owner_pid=record["pid"])
        _local.record, _local.pid, _local.handle = record, os.getpid(), handle
        yield record
    finally:
        _local.record = _local.handle = None
        if handle is not None:
            with _guard():
                handle.close()  # OS releases the lifetime lock before removing the record.
                path.unlink(missing_ok=True)
                _event("released", ticket=path.name, elapsed_seconds=round(time.monotonic() - started, 3))


acquire = lease


def main(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    if not argv:
        print(__doc__)
        return 2
    from pipeline.io_utils import _WindowsJob

    with lease(" ".join(argv)[:300]) as record:
        env = {**os.environ, _INHERITED: str((Path(SLOT_DIR) / "queue" / record["ticket"]).resolve())}
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        if os.name != "nt" and _local.handle is not None:
            kwargs["pass_fds"] = (_local.handle.fileno(),)
        child = job = None
        try:
            child = subprocess.Popen(argv, env=env, **kwargs)
            job = _WindowsJob(child)
            return child.wait()
        finally:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            if job is not None:
                job.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
