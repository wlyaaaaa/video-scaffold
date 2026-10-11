"""整机出片排队：同时出片的数量和可用内存都够了才放行。

多个会话、多个工作副本同时出片时，每段出片又会开好几路编码，一起跑会把内存撑满。
把出片命令套进这个脚本即可：

    python -m pipeline.render_queue -- python -m pipeline.pages <分镜表> render

- 全机最多同时放行 VIDEO_RENDER_SLOTS 个（默认 2）；
- 已有出片在跑时，可用内存低于 VIDEO_RENDER_MIN_FREE_GB（默认 14）就先等；
  没有别的出片在跑时直接放行，免得一直等不到；
- 名额是系统临时目录里的锁文件，持有进程退出后自动作废；
- 子命令的退出码原样返回。
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import time

SLOTS = int(os.environ.get("VIDEO_RENDER_SLOTS", "2"))
MIN_FREE_GB = float(os.environ.get("VIDEO_RENDER_MIN_FREE_GB", "14"))
SLOT_DIR = os.environ.get(
    "VIDEO_RENDER_SLOT_DIR",
    os.path.join(tempfile.gettempdir(), "video-scaffold-render-slots"),
)
POLL_SECONDS = 5
REPORT_SECONDS = 30


def free_gb():
    if os.name != "nt":
        try:
            with open("/proc/meminfo", encoding="ascii") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) / 1024 / 1024
        except OSError:
            pass
        return float("inf")

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return status.ullAvailPhys / 1024**3


def alive(pid):
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    code = ctypes.c_ulong()
    ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    kernel32.CloseHandle(handle)
    return bool(ok) and code.value == 259  # STILL_ACTIVE


def holder(path):
    try:
        with open(path, encoding="utf-8") as f:
            return int(f.readline().strip() or 0)
    except (OSError, ValueError):
        return 0


def busy_slots():
    """清掉持有进程已退出的锁，返回仍在用的名额数。"""
    used = 0
    for i in range(SLOTS):
        path = os.path.join(SLOT_DIR, f"slot-{i}.lock")
        if not os.path.exists(path):
            continue
        if alive(holder(path)):
            used += 1
        else:
            try:
                os.remove(path)
            except OSError:
                pass
    return used


def try_take(label):
    for i in range(SLOTS):
        path = os.path.join(SLOT_DIR, f"slot-{i}.lock")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()}\n{time.strftime('%Y-%m-%d %H:%M:%S')}\n{label}\n")
        return path
    return None


def acquire(label):
    os.makedirs(SLOT_DIR, exist_ok=True)
    last_report = 0.0
    while True:
        used = busy_slots()
        free = free_gb()
        if used < SLOTS and (used == 0 or free >= MIN_FREE_GB):
            path = try_take(label)
            if path:
                print(f"[出片排队] 放行：可用内存 {free:.1f} GB，同时出片 {used + 1}/{SLOTS}", flush=True)
                return path
        now = time.monotonic()
        if now - last_report >= REPORT_SECONDS:
            print(
                f"[出片排队] 等待：正在出片 {used}/{SLOTS}，可用内存 {free:.1f} GB"
                f"（有别的出片在跑时需 ≥ {MIN_FREE_GB:g} GB）",
                flush=True,
            )
            last_report = now
        time.sleep(POLL_SECONDS)


def main(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    if not argv:
        print(__doc__)
        return 2
    path = acquire(" ".join(argv)[:300])
    try:
        return subprocess.call(argv)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
