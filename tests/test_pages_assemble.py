import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pipeline import pages_assemble as assembly

def run(*args):
    return subprocess.check_output(args, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

class PagesAssembleTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / ".test-temp"
        base.mkdir(exist_ok=True)
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="assemble-", dir=base)))
        self.enterContext(patch.dict(os.environ, dict(TEMP=str(self.root), TMP=str(self.root), TMPDIR=str(self.root))))
        self.enterContext(patch("pipeline.render_queue.SLOT_DIR", self.root / "slots"))
        self.manifest = self.root / "manifest.json"
        self.spec = dict(parts=[dict(id="a", path="a.mp4"), dict(id="b", path="b.mp4")],
                         chapters=[dict(title="开场", **{"from": "a"}), dict(title="收尾", **{"from": "b"})], max_title_chars=6)
        self.write()
        for name, duration, color in (("a", .5, "green"), ("b", .9, "blue")):
            run("ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                f"color=c={color}:s=320x180:r=60:d={duration}", "-f", "lavfi", "-i",
                f"sine=frequency=440:sample_rate=48000:duration={duration}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", str(duration), str(self.root / f"{name}.mp4"))
    def write(self):
        self.manifest.write_text(json.dumps(self.spec, ensure_ascii=False), encoding="utf-8")
    def test_plan_is_read_only_and_validates_chapters(self):
        for out in (None, "existing.mp4"):
            if out is not None:
                self.spec["out"] = out
                (self.root / out).write_bytes(b"original")
                self.write()
            before = {p: p.read_bytes() for p in self.root.iterdir()}
            plan = assembly.plan(self.manifest)
            self.assertEqual((plan["fps"], plan["total_frames"], [c["frame"] for c in plan["chapters"]]), (60, 84, [0, 30]))
            self.assertEqual(before, {p: p.read_bytes() for p in self.root.iterdir()})
        for chapters in ([{"title": "晚", "from": "b"}], [{"title": "", "from": "a"}],
                         [{"title": "一二三四五六七", "from": "a"}], [{"title": "首", "from": "a"}, {"title": "复", "from": "a"}]):
            self.spec["chapters"] = chapters
            self.write()
            with self.subTest(chapters=chapters), self.assertRaises(ValueError):
                assembly.plan(self.manifest)
    def test_real_join_keeps_frame_duration_and_refuses_overwrite(self):
        self.spec["out"] = "joined.mp4"
        self.write()
        before = {p: p.read_bytes() for p in self.root.iterdir()}
        result = assembly.assemble(self.manifest)
        info = json.loads(run("ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(self.root / "joined.mp4")))
        self.assertEqual(int(next(s for s in info["streams"] if s["codec_type"] == "video")["nb_read_frames"]), 84)
        for stream in [info["format"], *info["streams"]]:
            self.assertLess(abs(float(stream["duration"]) - 1.4), 1 / 60)
        self.assertTrue(all(Path(result[key]).is_file() for key in ("chapters_path", "receipt_path")))
        before[Path(result["out"])] = Path(result["out"]).read_bytes()
        with self.assertRaises(FileExistsError):
            assembly.assemble(self.manifest)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
