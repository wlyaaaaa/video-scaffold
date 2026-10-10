"""Real FFmpeg color samples; CPU substitution tests math, not NVENC hardware."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from webfilm import render
from webfilm.common import run, tool


class HardwareColorTests(unittest.TestCase):
    def patch_video(self, root, name, *, color_range="pc", transfer="iec61966-2-1", tagged=True):
        values = (0, 128, 255) if color_range == "pc" else (16, 126, 235)
        raw = b"".join(bytes([v])*64 for v in values)*64 + bytes([128])*6144
        tags = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", transfer,
                "-color_range", color_range] if tagged else []
        if tagged: tags += ["-vf", f"setparams=range={color_range}:color_primaries=bt709:color_trc={transfer}:colorspace=bt709"]
        path = root / name
        run([tool("ffmpeg"), "-v", "error", "-f", "rawvideo", "-pixel_format", "yuv420p",
             "-video_size", "192x64", "-framerate", "60", "-i", "pipe:0", "-frames:v", "1",
             "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0", *tags, path], input=raw)
        return path, values

    def software_encode(self, arguments, **kwargs):
        arguments = list(arguments)
        begin, end = arguments.index("-c:v"), arguments.index("-pix_fmt")
        arguments[begin:end] = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "0"]
        at = arguments.index("-profile:v")
        del arguments[at:at+2]
        return run(arguments, **kwargs)

    def test_black_white_gray_samples_really_convert_range_and_transfer(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            for color_range in ("pc", "tv"):
                with self.subTest(color_range=color_range):
                    source, values = self.patch_video(root, color_range+".mkv", color_range=color_range)
                    with mock.patch.object(render, "run", side_effect=self.software_encode):
                        output, evidence = render.normalize_hardware_color(source, root, 60)
                    decoded = run([tool("ffmpeg"), "-v", "error", "-i", output, "-frames:v", "1",
                                   "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"]).stdout
                    samples = [decoded[32*192+x] for x in (32, 96, 160)]
                    range_only = round(16+219*values[1]/255) if color_range == "pc" else values[1]
                    for actual, wanted in ((samples[0], 16), (samples[2], 235)):
                        self.assertLessEqual(abs(actual-wanted), 2)
                    self.assertTrue(16 < samples[1] < 235)
                    self.assertGreater(abs(samples[1]-range_only), 2)
                    self.assertTrue(evidence["converted"])
                    self.assertEqual(evidence["target"], render.BT709_TV)
                    self.assertIn("tin=iec61966-2-1:rin="+color_range, evidence["filter"])

    def test_exact_bt709_tv_skips_and_unknown_color_fails(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            source, _ = self.patch_video(root, "standard.mkv", color_range="tv", transfer="bt709")
            original = source.read_bytes()
            with mock.patch.object(render, "run", side_effect=AssertionError("Already standard must not encode")):
                output, evidence = render.normalize_hardware_color(source, root, 60)
            self.assertEqual(output, source)
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse(evidence["converted"])
            unknown, _ = self.patch_video(root, "unknown.mkv", tagged=False)
            with self.assertRaises(ValueError):
                render.normalize_hardware_color(unknown, root, 60)
