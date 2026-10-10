"""Conservative Canvas2D capture and the standalone LocalGpuBroker adapter."""
from __future__ import annotations

import base64
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler
import uuid

from .browser import assert_runtime, evaluate
from .common import machine_profile


class CanvasUnsupported(RuntimeError):
    """The page/configuration requires the screenshot capture path."""


class HardwareLease:
    def __init__(self, url):
        self.url, self.token, self.error = url.rstrip("/"), "", None
        self.stop = threading.Event()

    def request(self, action, **payload):
        request = Request(self.url + "/_gpu_broker/" + action,
                          data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with build_opener(ProxyHandler({})).open(request, timeout=20) as response:
                result = json.load(response)
        except HTTPError as error:
            try:
                result = json.load(error)
            except (ValueError, OSError):
                raise RuntimeError(f"GPU broker HTTP {error.code}") from error
        if not result.get("ok"):
            raise RuntimeError("GPU broker: " + str(result.get("reason", "unavailable")))
        return result

    def check(self):
        if self.error:
            raise RuntimeError(f"GPU lease lost: {self.error}")

    def renew(self):
        while not self.stop.wait(100):
            try:
                self.request("renew", token=self.token, ttl_seconds=300, owner_pid=os.getpid())
            except Exception as error:
                self.error = error
                self.stop.set()


_local = threading.local()


@contextmanager
def hardware_lease():
    lease = HardwareLease(os.environ.get("WEBFILM_GPU_BROKER") or machine_profile().get("gpu_broker_url", ""))
    if not lease.url:
        yield lease
        return
    lease.token = lease.request("acquire", owner="webfilm", owner_pid=os.getpid(), ttl_seconds=300)["token"]
    thread = threading.Thread(target=lease.renew, name="webfilm-gpu-lease", daemon=True)
    _local.lease = lease
    thread.start()
    try:
        yield lease
        lease.check()
    finally:
        original = sys.exception()
        _local.lease = None
        lease.stop.set()
        thread.join(timeout=22)
        try:
            lease.request("release", token=lease.token)
        except Exception as error:
            if original is None:
                raise
            original.add_note(f"GPU lease release also failed: {error}")


@contextmanager
def canvas_session(page):
    try:
        yield
    finally:
        evaluate(page, "() => {const s=window.__WEBFILM_ENCODER_SESSION__; try {if(s?.encoder.state!=='closed')s?.encoder.close();} finally {delete window.__WEBFILM_ENCODER_SESSION__;}}")


def capture_canvas(page, runtime, output, fps, start_frame, end_frame, *, cached=None, verify_frames=False, keep_encoder=False,
                   sample_frames=None):
    """Write Annex B H264, retaining hashes of the exact opaque RGB inputs."""
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
        raise ValueError("fps must be finite and positive")
    if any(type(n) is not int for n in (start_frame, end_frame)) or not 0 <= start_frame < end_frame:
        raise ValueError("Canvas capture requires a nonempty integer frame range")
    expected = [math.floor(i*1_000_000/fps + 0.5) for i in range(end_frame-start_frame)]
    if not verify_frames:
        cached = None
    if cached is not None and len(cached["frames"]) != len(expected):
        raise ValueError("Cached frame count does not match capture range")
    output, timestamps, binding = Path(output), [], "__webfilm_write_" + uuid.uuid4().hex
    elapsed = time.perf_counter()
    lease = runtime.get("lease") or getattr(_local, "lease", None)
    assert_runtime(page, runtime)
    device = {"available": False}
    try:
        client = page.context.browser.new_browser_cdp_session()
        try:
            gpu = client.send("SystemInfo.getInfo")["gpu"]
            device = {"available": True, "devices": gpu.get("devices", []),
                      "feature_status": gpu.get("featureStatus", {})}
        finally:
            client.detach()
    except Exception as error:
        device["reason"] = str(error)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        def receive(message):
            if lease:
                lease.check()
            errors = runtime["blocked"] + runtime["failures"]
            if errors:
                raise ValueError("Work runtime failed: " + "; ".join(dict.fromkeys(errors)))
            if message["kind"] == "chunk":
                for timestamp in message["timestamps"]:
                    at = len(timestamps)
                    if at >= len(expected) or timestamp != expected[at]:
                        raise ValueError("Encoder output frame timestamp/count mismatch")
                    timestamps.append(timestamp)
                handle.write(base64.b64decode(message["data"], validate=True))
        page.expose_function(binding, receive)
        try:
            result = evaluate(page, Path(__file__).with_suffix(".js").read_text(encoding="utf-8"),
                              {"fps": fps, "start": start_frame, "end": end_frame, "binding": binding,
                               "cached": cached["frames"] if cached is not None else None, "verifyFrames": verify_frames, "sampleFrames": sample_frames,
                               "keepEncoder": keep_encoder},
                              timeout=max(120, len(expected)*5))
        finally:
            # Functions have unique names because Playwright has no remove_exposed_function.
            evaluate(page, "name => { delete window[name]; }", binding)
        if result.get("unsupported"):
            raise CanvasUnsupported(result["unsupported"])
        if not result["reused"] and timestamps != expected:
            raise ValueError("Encoder did not output every input frame")
    assert_runtime(page, runtime)
    if result["reused"]:
        shutil.copyfile(cached["video"], output)
        result["evidence"]["reused_encoding"] = cached.get("evidence", {})
    result["evidence"].update(device=device, chunk_timestamps_us=timestamps, chunk_count=len(timestamps),
                              hardware_preference="prefer-hardware (request; actual encoder is not exposed)")
    result.setdefault("timing", {}).update(capture_seconds=time.perf_counter()-elapsed, encoded_frames=len(timestamps))
    return result
