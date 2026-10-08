"""Absolute source clocks, action replay, and PCM/master range regressions."""
import os
from pathlib import Path
import struct
import unittest
import wave

from webfilm.common import read_json, sha256, temp_workspace, write_json
from webfilm.render import compare_renders, crop_pcm, frame_range, render_stills, render_work, reusable_soundtrack


def write_pcm(path, seconds=1):
    count = round(seconds*48000)
    raw = struct.pack("<hh", 1000, 2000)*(count//2) + struct.pack("<hh", -3000, -4000)*(count-count//2)
    with wave.open(str(path), "wb") as pcm:
        pcm.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
        pcm.writeframes(raw)
    return raw


class PreviewTests(unittest.TestCase):
    def test_range_uses_original_frame_grid_and_rejects_invalid_values(self):
        self.assertEqual(frame_range(20), (0, 1200))
        self.assertEqual(frame_range(20, 60, 1.5, 3), (90, 180))
        self.assertEqual(frame_range(20, 60, 1/60, 2/60), (1, 2))
        for start, end in ((float("nan"), 2), (0, float("inf")), (-1, 2), (1, 1), (2, 1),
                           (19, 21), (True, 2), (0.01, 0.11), (0, 0.011)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                frame_range(20, 60, start, end)

    def test_pcm_crop_preserves_source_samples_and_segment_origin(self):
        with temp_workspace(Path(__file__).parent, "preview-test-") as root:
            master, segment, same = root / "full.wav", root / "segment.wav", root / "same.wav"
            raw = write_pcm(master)
            crop_pcm(master, segment, [0.5, 0.75], [0, 1])
            with wave.open(str(segment), "rb") as pcm:
                self.assertEqual(pcm.getparams()[:3], (2, 2, 48000))
                self.assertEqual(pcm.getnframes(), 12000)
                self.assertEqual(pcm.readframes(12000), raw[24000*4:36000*4])
            crop_pcm(segment, same, [0.5, 0.75], [0.5, 0.75])
            self.assertEqual(segment.read_bytes(), same.read_bytes())
            with self.assertRaises(ValueError):
                crop_pcm(segment, same, [0, 0.25], [0.5, 0.75])
            with self.assertRaises(ValueError):
                crop_pcm(master, same, [0.5, 0.75], [0, 2])

    def test_master_reuse_never_confuses_same_length_ranges(self):
        files = [{"path": "index.html", "sha256": "current-source"}]
        with temp_workspace(Path(__file__).parent, "preview-test-") as root:
            video = root / "a-segment.mp4"
            video.write_bytes(b"source-bound video fixture")
            wav = Path(str(video) + ".wav")
            write_pcm(wav, 0.5)
            identity = {"schema": "webfilm.render.v1", "width": 1920, "height": 1080, "duration": 0.5,
                        "source_duration": 2, "source_range": [0.5, 1], "action_script_sha256": None,
                        "work": {"pass": True, "files": files, "runtime": {"chrome": "test"}},
                        "audio": {"sha256": sha256(wav), "source_duration": 2, "source_range": [0.5, 1]},
                        "output_sha256": sha256(video)}
            write_json(str(video) + ".json", identity)
            arguments = (root, {"files": files}, {"duration": 2}, 1920, 1080, None, "test", False)
            self.assertIsNone(reusable_soundtrack(*arguments))
            self.assertIsNone(reusable_soundtrack(*arguments, start=1, end=1.5))
            self.assertEqual(reusable_soundtrack(*arguments, start=0.5, end=1)[0], wav)
            identity["audio"]["source_range"] = [1, 1.5]
            write_json(str(video) + ".json", identity)
            self.assertIsNone(reusable_soundtrack(*arguments, start=0.5, end=1))
            identity["audio"]["source_range"] = [0.5, 1]
            write_json(str(video) + ".json", identity)
            full = root / "z-full.mp4"
            full.write_bytes(b"full source-bound fixture")
            full_wav = Path(str(full) + ".wav")
            write_pcm(full_wav, 2)
            # A legacy whole-render identity is still an unambiguous full master.
            identity.update(duration=2, output_sha256=sha256(full), audio={"sha256": sha256(full_wav)})
            identity.pop("source_range")
            identity.pop("source_duration")
            write_json(str(full) + ".json", identity)
            self.assertEqual(reusable_soundtrack(*arguments, start=0.5, end=1)[0], full_wav)
            self.assertIsNone(reusable_soundtrack(root, {"files": files}, {"duration": 3}, 1920, 1080, None, "test", False))

    def test_compare_rejects_identical_pixels_at_different_source_times(self):
        with temp_workspace(Path(__file__).parent, "preview-test-") as root:
            paths = [root / "a.mp4", root / "b.mp4"]
            for path, interval in zip(paths, ([0, 1], [1, 2])):
                path.write_bytes(b"same encoded fixture")
                wav = Path(str(path) + ".wav")
                write_pcm(wav)
                frames = {"width": 1920, "height": 1080, "fps": 60, "duration": 1,
                          "source_duration": 2, "source_range": interval, "sha256": ["same-pixels"]}
                write_json(str(path) + ".frames.json", frames)
                write_json(str(path) + ".json", {"duration": 1, "source_duration": 2, "source_range": interval,
                                                "audio": {"sha256": sha256(wav)}, "output_sha256": sha256(path),
                                                "frames_sha256": sha256(str(path) + ".frames.json")})
            result = compare_renders(*paths)
            self.assertFalse(result["pass"])
            self.assertFalse(result["source_ranges_equal"])
            self.assertEqual(result["mismatched_frames"], [])

    @unittest.skipUnless(os.environ.get("WEBFILM_PREVIEW_BROWSER_TESTS") == "1", "opt-in installed Chrome/FFmpeg integration")
    def test_whole_segment_and_stills_preserve_prestart_actions_and_pcm(self):
        with temp_workspace(Path(__file__).parent, "preview-browser-") as root:
            work = root / "work"
            work.mkdir()
            write_json(work / "work.json", {"schema": 1, "entry": "index.html", "duration": 1, "audio": "generated"})
            (work / "index.html").write_text("""<!doctype html><style>
              body{margin:0;height:2200px}canvas{position:fixed;inset:0;width:100%;height:100%}
              button{position:absolute;top:20px;left:20px;z-index:2}</style>
              <canvas id="c" width="1920" height="1080"></canvas><button id="b">Click</button><script>
              let clicks=0, clickedAt=-1; b.onclick=()=>{clicks++;clickedAt=window.__WEBFILM_TIME__};
              window.webfilm={duration:1,render(t){
                const x=c.getContext('2d');x.fillStyle=clicks?'#397452':'#983124';x.fillRect(0,0,1920,1080);
                x.fillStyle='#ffffff';x.fillRect(Math.round(t*900),Math.round(clickedAt*600)+100,60,60);
                b.style.visibility=t<.3?'visible':'hidden';
              },audio(ctx){const o=ctx.createOscillator(),g=ctx.createGain();o.frequency.setValueAtTime(220,0);
                o.frequency.setValueAtTime(440,.5);g.gain.value=.1;o.connect(g);g.connect(ctx.destination);o.start(0);o.stop(1);}};
              </script>""", encoding="utf-8")
            actions = work / "actions.json"
            write_json(actions, {"schema": 1, "actions": [{"at": 0.01, "type": "click", "selector": "#b"},
                                                          {"at": 0.1, "type": "scroll", "y": 200, "duration": 0.3}]})
            full, part = root / "full.mp4", root / "part.mp4"
            complete = render_work(work, full, width=1920, height=1080, actions_path=actions)
            segment = render_work(work, part, width=1920, height=1080, actions_path=actions, start=0.5, end=0.75)
            self.assertEqual(complete["duration"], 1)
            self.assertEqual(complete["frame_count"], 60)
            self.assertEqual(read_json(str(part)+".frames.json")["sha256"], read_json(str(full)+".frames.json")["sha256"][30:45])
            self.assertEqual(segment["work"]["runtime"]["action_log"][0]["frame_time"], 1/60)
            self.assertEqual(segment["frame_count"], 15)
            with wave.open(str(full)+".wav", "rb") as pcm:
                pcm.setpos(24000)
                expected = pcm.readframes(12000)
            with wave.open(str(part)+".wav", "rb") as pcm:
                self.assertEqual(pcm.getnframes(), 12000)
                self.assertEqual(pcm.readframes(12000), expected)
            stills = render_stills(work, root / "stills", at=[0.7, 0.5, 0.6], width=1920, height=1080, actions_path=actions)
            hashes = read_json(str(full)+".frames.json")["sha256"]
            self.assertEqual([f["pixels_sha256"] for f in stills["files"]], [hashes[30], hashes[36], hashes[42]])
            self.assertEqual(stills["work"]["runtime"]["action_log"][0]["frame_time"], 1/60)
            self.assertEqual(read_json(work / "work.json")["duration"], 1)
            with self.assertRaises(FileExistsError):
                render_stills(work, root / "stills", at=[0.5], width=1920, height=1080)
