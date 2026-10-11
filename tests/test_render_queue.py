"""Exercise real queue locks with isolated, lightweight child processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

HOLDER = """import sys,time
from pathlib import Path
from pipeline import render_queue as q
q.POLL_SECONDS=.02
root,label=Path(sys.argv[1]),sys.argv[2]
with q.lease(label):
 (root/(label+'.entered')).write_text(label)
 while not (root/(label+'.release')).exists(): time.sleep(.01)
"""

class RenderQueueTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / ".test-temp"
        base.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="render-queue-", dir=base)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = dict(os.environ, VIDEO_RENDER_SLOT_DIR=str(self.root / "slots"),
                        VIDEO_RENDER_SLOTS="1", VIDEO_RENDER_MIN_FREE_GB="0",
                        TEMP=str(self.root), TMP=str(self.root), TMPDIR=str(self.root),
                        PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("VIDEO_RENDER_WORKERS", None)
        self.env.pop("VIDEO_RENDER_QUEUE_LEASE", None)

    @staticmethod
    def _stop(process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)

    def _start(self, code, *args, cli=False):
        command = [sys.executable, "-B", "-c", code, *map(str, args)]
        if cli:
            command = [sys.executable, "-B", "-m", "pipeline.render_queue", "--", *command]
        process = subprocess.Popen(command, env=self.env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.addCleanup(self._stop, process)
        return process

    def _wait(self, predicate):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.02)
        self.fail("queue handshake timed out")

    def _exit(self, process, expected=0):
        output, error = process.communicate(timeout=10)
        self.assertEqual(process.returncode, expected, output + error)

    def _states(self):
        records = []
        for path in (self.root / "slots" / "queue").glob("*.ticket"):
            try:
                with path.open("rb") as stream:
                    stream.seek(1)
                    records.append(json.loads(stream.read()))
            except (OSError, ValueError):
                pass
        return records

    def test_fifo_and_killed_holder_releases_slot(self):
        first = self._start(HOLDER, self.root, "first")
        self._wait(lambda: (self.root / "first.entered").exists())
        second = self._start(HOLDER, self.root, "second")
        self._wait(lambda: any(r["label"] == "second" and r["state"] == "waiting" for r in self._states()))
        third = self._start(HOLDER, self.root, "third")
        self._wait(lambda: any(r["label"] == "third" and r["state"] == "waiting" for r in self._states()))
        self.assertFalse((self.root / "second.entered").exists())
        first.kill()
        first.wait(timeout=5)
        self._wait(lambda: (self.root / "second.entered").exists())
        self.assertFalse((self.root / "third.entered").exists())
        (self.root / "second.release").touch()
        self._exit(second)
        self._wait(lambda: (self.root / "third.entered").exists())
        (self.root / "third.release").touch()
        self._exit(third)
        self.assertEqual(list((self.root / "slots" / "queue").glob("*.ticket")), [])

    def test_nested_and_cli_lease_share_one_ticket_and_exit_code(self):
        code = "from pathlib import Path\nfrom pipeline import render_queue as q\nwith q.lease('outer') as outer:\n with q.acquire('inner') as inner:\n  assert outer is inner and outer['state']=='active'\n  assert len(list((Path(q.SLOT_DIR)/'queue').glob('*.ticket')))==1\n"
        self._exit(self._start(code))
        self._exit(self._start(code + "raise SystemExit(23)\n", cli=True), 23)

    def test_workers_override_boundaries_and_unknown_memory(self):
        code = "from pipeline import render_queue as q\nimport os\nq.SLOTS=2\nq.MIN_FREE_GB=14\nassert [q.auto_workers(v) for v in (-1,14,19.99,20,26,99)]==[1,1,1,1,2,4]\nfor value in (0.0,float('nan')):\n q.free_gb=lambda:value\n assert q.auto_workers()==1\nos.environ['VIDEO_RENDER_WORKERS']='7'\nassert q.auto_workers(0)==7\n"
        self._exit(self._start(code))
