"""Optional adapter for the existing LocalGpuBroker, no new GPU service."""

from __future__ import annotations
from contextlib import contextmanager
import json
import os
import threading
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
import config


class Lease:
    def __init__(self):
        self.token = ""
        self.error = None
        self.stop = threading.Event()
        self.thread = None

    def request(self, action, **payload):
        url = config.GPU_BROKER_URL.rstrip("/") + "/_gpu_broker/" + action
        request = Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with build_opener(ProxyHandler({})).open(request, timeout=20) as response:
                result = json.load(response)
        except HTTPError as error:
            try:
                result = json.load(error)
            except Exception:
                raise RuntimeError(f"GPU broker HTTP {error.code}") from error
        if not result.get("ok"):
            raise RuntimeError(
                "GPU broker: " + str(result.get("reason", "unavailable"))
            )
        return result

    def check(self):
        if self.error:
            raise RuntimeError(f"GPU lease lost: {self.error}")

    def renew(self):
        while not self.stop.wait(max(5, config.GPU_LEASE_SECONDS / 3)):
            try:
                self.request(
                    "renew", token=self.token, ttl_seconds=config.GPU_LEASE_SECONDS
                )
            except Exception as error:
                self.error = error
                self.stop.set()


_local = threading.local()


@contextmanager
def gpu_lease(required=True):
    existing = getattr(_local, "lease", None)
    if existing is not None:
        existing.check()
        yield existing
        existing.check()
        return
    lease = Lease()
    if not required or not config.GPU_BROKER_URL:
        yield lease
        return
    result = lease.request(
        "acquire",
        owner="video-scaffold",
        owner_pid=os.getpid(),
        ttl_seconds=config.GPU_LEASE_SECONDS,
    )
    lease.token = result["token"]
    lease.thread = threading.Thread(
        target=lease.renew, name="video-gpu-lease", daemon=True
    )
    _local.lease = lease
    lease.thread.start()
    try:
        yield lease
        lease.check()
    finally:
        _local.lease = None
        lease.stop.set()
        lease.thread.join(timeout=22)
        import sys

        original_error = sys.exception()
        try:
            lease.request("release", token=lease.token)
        except Exception as release_error:
            if original_error is not None:
                original_error.add_note(
                    f"GPU lease release also failed: {release_error}"
                )
            else:
                raise
