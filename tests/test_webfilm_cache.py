"""Interrupted checkpoints, scene invalidation, and honest sampled evidence."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from contextlib import nullcontext

from webfilm.cache import capture_segments, scene_ranges
from webfilm.common import sha256, write_json
from webfilm.render import compare_renders


class CacheTests(unittest.TestCase):
    def test_interruption_scene_edit_and_corrupted_segment(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as directory:
            parent = Path(directory)
            temporary = parent / "temporary"
            temporary.mkdir()
            config = {"duration": 4, "render_segments": [{"start": 0, "end": 2, "files": ["a.js"]},
                                                         {"start": 2, "end": 4, "files": ["b.js"]}]}
            report = {"files": [{"path": "index.html", "sha256": "global"}, {"path": "a.js", "sha256": "a"},
                                {"path": "b.js", "sha256": "b"}]}
            captured, fail = [], [True]
            def capture(page, runtime, output, fps, first, last, **kwargs):
                captured.append(first)
                if first == 120 and fail[0]:
                    raise RuntimeError("interrupted second segment")
                output.write_bytes(f"encoded {first} {report['files']}".encode())
                return {"frames": ["first", "middle", "last"], "frame_indices": [first, first+60, last-1],
                        "evidence": {"decoder_color_space": {"matrix": "bt709", "primaries": "bt709",
                                       "transfer": "iec61966-2-1", "fullRange": False}}, "timing": {}}
            def run(args):
                output = Path(args[-1])
                if "concat" in args:
                    output.write_bytes(b"joined verified segments")
                else:
                    output.write_bytes(Path(args[args.index("-i")+1]).read_bytes())
            def execute(name):
                return capture_segments(None, {"chrome": "fixture"}, parent, report, config, parent, temporary,
                                        parent/name, 3840, 2160, 60, 0, 240)
            with patch('webfilm.webcodecs.capture_canvas', capture), patch('webfilm.cache.run', run), \
                    patch('webfilm.webcodecs.canvas_session', return_value=nullcontext()), \
                    patch('webfilm.cache.tool', return_value='ffmpeg'), patch('webfilm.check.check_work', side_effect=lambda *a, **k: report), \
                    patch('webfilm.cache.probe', return_value={"streams": [{"codec_type": "video", "nb_frames": "120",
                          "width": 3840, "height": 2160, "has_b_frames": 0, "duration": "2"}]}):
                with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                    execute('failed.mp4')
                fail[0] = False
                captured.clear()
                _, evidence = execute('resumed.mp4')
                self.assertEqual(captured, [120])
                self.assertEqual([s['reused'] for s in evidence['segments']], [True, False])
                original = evidence['segments'][1]['produced_from']
                report['files'] = [dict(f, sha256='changed') if f['path']=='a.js' else f for f in report['files']]
                captured.clear()
                _, evidence = execute('edited.mp4')
                self.assertEqual(captured, [0])
                self.assertEqual(evidence['segments'][1]['reuse_basis'], 'author scene dependencies')
                self.assertEqual(evidence['segments'][1]['produced_from'], original)
                (Path(evidence['cache'])/'120-240.mp4').write_bytes(b'corrupt')
                captured.clear()
                execute('rebuilt.mp4')
                self.assertEqual(captured, [120])

    def test_scene_declaration_rejects_gaps_and_unknown_dependencies(self):
        files = [{"path": "a.js"}]
        for scenes in ([{"start": 0, "end": 1, "files": []}], [{"start": 0, "end": 2, "files": ["missing"]}]):
            with self.assertRaises(ValueError):
                list(scene_ranges({"duration": 2, "render_segments": scenes}, files, 60, 0, 120))

    def test_comparison_reports_samples_without_claiming_all_source_pixels(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as directory:
            parent = Path(directory)
            a, b = parent/'a.mp4', parent/'b.mp4'
            for video, indices in ((a, [0, 1, 2]), (b, [0, 2])):
                video.write_bytes(b'unit byte binding fixture')
                Path(str(video)+'.wav').write_bytes(b'PCM fixture')
                write_json(str(video)+'.frames.json', {"width": 3840, "height": 2160, "fps": 60, "duration": .05,
                           "frame_count": 3, "frame_indices": indices, "sha256": [str(i) for i in indices]})
                write_json(str(video)+'.json', {"audio": {"sha256": sha256(str(video)+'.wav')}, "output_sha256": sha256(video),
                           "frames_sha256": sha256(str(video)+'.frames.json')})
            comparison = compare_renders(a, b)
            self.assertTrue(comparison['pass'])
            self.assertFalse(comparison['all_source_frames_compared'])
            self.assertEqual(comparison['sampled_frame_indices'], [0, 2])
