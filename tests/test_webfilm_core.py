"""Meaningful clock, work-rule, and deterministic comparison regression checks."""
import json
from pathlib import Path
import unittest

from helpers import windows_recycle_fixture
from webfilm.check import check_work, load_work
from webfilm.common import sha256, temp_workspace, write_json
from webfilm.render import compare_renders, frame_count, load_actions, reusable_soundtrack


class WebfilmCoreTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(windows_recycle_fixture())

    def work(self, root, body="<p>local page</p>"):
        root.mkdir()
        write_json(root / "work.json", {"schema": 1, "entry": "index.html", "duration": 20, "audio": "none"})
        (root / "index.html").write_text(body, encoding="utf-8")

    def test_clock_and_out_of_range_actions(self):
        self.assertEqual(frame_count(20, 60), 1200)
        with self.assertRaises(ValueError):
            frame_count(0.011, 60)
        with temp_workspace(Path(__file__).parent, "webfilm-test-") as root:
            path = root / "actions.json"
            write_json(path, {"schema": 1, "actions": [{"at": 2, "type": "scroll", "y": 100, "duration": 30}]})
            with self.assertRaises(ValueError):
                load_actions(path, 20)

    def test_rules_catch_network_missing_assets_and_disguised_audio(self):
        with temp_workspace(Path(__file__).parent, "webfilm-test-") as root:
            work = root / "work"
            self.work(work, '<script src="https://example.test/x.js"></script><img src="missing.png">')
            (work / "not-a-track.bin").write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
            report = check_work(work)
            self.assertFalse(report["pass"])
            self.assertTrue(any("external resource" in error for error in report["errors"]))
            self.assertTrue(any("missing" in error for error in report["errors"]))
            self.assertTrue(any("prerecorded" in error for error in report["errors"]))

    def test_oversized_duration_and_entry_escape_fail(self):
        with temp_workspace(Path(__file__).parent, "webfilm-test-") as root:
            work = root / "work"
            self.work(work)
            write_json(work / "work.json", {"schema": 1, "duration": 121, "entry": "index.html"})
            with self.assertRaises(ValueError):
                load_work(work)
            write_json(work / "work.json", {"schema": 1, "duration": 20, "entry": "../index.html"})
            with self.assertRaises(ValueError):
                load_work(work)

    def test_comparison_detects_changed_frame_or_pcm(self):
        with temp_workspace(Path(__file__).parent, "webfilm-test-") as root:
            a, b = root / "a.mp4", root / "b.mp4"
            frames = {"width": 3840, "height": 2160, "fps": 60, "duration": 20, "sha256": ["a", "b"]}
            for path in (a, b):
                path.write_bytes(b"unit fixture: only source binding is being tested")
                Path(str(path) + ".wav").write_bytes(b"unit fixture PCM")
                write_json(str(path) + ".frames.json", frames)
                write_json(str(path) + ".json", {"audio": {"sha256": sha256(str(path) + ".wav")},
                                                "output_sha256": sha256(path), "frames_sha256": sha256(str(path) + ".frames.json")})
            self.assertTrue(compare_renders(a, b)["pass"])
            frames["sha256"] = ["a", "changed"]
            write_json(str(b) + ".frames.json", frames)
            identity = json.loads(Path(str(b) + ".json").read_text())
            identity["frames_sha256"] = sha256(str(b) + ".frames.json")
            write_json(str(b) + ".json", identity)
            self.assertEqual(compare_renders(a, b)["mismatched_frames"], [1])
            write_json(str(b) + ".frames.json", dict(frames, sha256=["a", "b"]))
            identity["frames_sha256"] = sha256(str(b) + ".frames.json")
            Path(str(b) + ".wav").write_bytes(b"changed PCM")
            identity["audio"]["sha256"] = sha256(str(b) + ".wav")
            write_json(str(b) + ".json", identity)
            self.assertFalse(compare_renders(a, b)["pass"])
            b.write_bytes(b"replaced output")
            with self.assertRaises(ValueError):
                compare_renders(a, b)

    def test_audio_master_reuse_requires_current_work_and_audio_bytes(self):
        with temp_workspace(Path(__file__).parent, "webfilm-test-") as root:
            video = root / "first.mp4"
            video.write_bytes(b"source-bound unit fixture")
            wav = root / "first.mp4.wav"
            wav.write_bytes(b"original master PCM")
            files = [{"path": "index.html", "sha256": "source-one"}]
            record = {"schema": "webfilm.render.v1", "width": 1920, "height": 1080, "duration": 20,
                      "action_script_sha256": None, "work": {"pass": True, "files": files, "runtime": {"chrome": "test"}},
                      "audio": {"sha256": sha256(wav)}, "output_sha256": sha256(video)}
            write_json(str(video) + ".json", record)
            result = reusable_soundtrack(root, {"files": files}, {"duration": 20}, 1920, 1080, None, "test", False)
            self.assertEqual(result[0], wav)
            self.assertEqual(result[1]["reused_from"]["soundtrack_sha256"], sha256(wav))
            self.assertIsNone(reusable_soundtrack(root, {"files": [{"path": "index.html", "sha256": "changed"}]},
                                                 {"duration": 20}, 1920, 1080, None, "test", False))
            record.update(capture_mode="external webpage clock", seed=829, entrypoint="a.html")
            write_json(str(video) + ".json", record)
            self.assertIsNotNone(reusable_soundtrack(root, {"files": files}, {"duration": 20, "seed": 829, "entry": "a.html"},
                                                    1920, 1080, None, "test", True))
            self.assertIsNone(reusable_soundtrack(root, {"files": files}, {"duration": 20, "seed": 829, "entry": "b.html"},
                                                 1920, 1080, None, "test", True))
            record.pop("entrypoint")
            write_json(str(video) + ".json", record)
            self.assertIsNone(reusable_soundtrack(root, {"files": files}, {"duration": 20, "seed": 829, "entry": "a.html"},
                                                 1920, 1080, None, "test", True))
            wav.write_bytes(b"replaced master")
            record.pop("capture_mode")
            write_json(str(video) + ".json", record)
            self.assertIsNone(reusable_soundtrack(root, {"files": files}, {"duration": 20}, 1920, 1080, None, "test", False))
