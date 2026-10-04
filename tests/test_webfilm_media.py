"""Postproduction semantics with synthetic CPU media, never real TTS evidence."""

from array import array
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import unittest

from PIL import Image

from webfilm import media
from webfilm.common import probe, run, sha256, temp_workspace, tool, write_json
from webfilm.package import package_site, upload_template


@contextmanager
def fixture():
    root = Path(os.environ.get("WEBFILM_TEST_TEMP", Path(__file__).resolve().parents[1] / ".cache"))
    with temp_workspace(root, "webfilm-test-") as temporary:
        yield Path(temporary)


def available_media_tools():
    try:
        tool("ffmpeg")
        tool("ffprobe")
        return True
    except FileNotFoundError:
        return False


def make_video(path, color, tone=None):
    arguments = [tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
                 "-f", "lavfi", "-i", f"color=c={color}:s=128x72:r=12:d=1.5"]
    if tone is not None:
        arguments += ["-f", "lavfi", "-i", f"sine=frequency={tone}:sample_rate=48000:duration=1.5",
                      "-c:a", "aac", "-ac", "2"]
    arguments += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1.5", str(path)]
    run(arguments)


def extract_frame(video, timestamp, target):
    run([tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-ss", str(timestamp),
         "-i", video, "-frames:v", "1", target])
    with Image.open(target) as frame:
        return frame.convert("RGB")


def tone_energy(samples, hz, sample_rate=48000):
    real = sum(value * math.cos(2 * math.pi * hz * index / sample_rate) for index, value in enumerate(samples))
    imaginary = sum(value * math.sin(2 * math.pi * hz * index / sample_rate) for index, value in enumerate(samples))
    return real * real + imaginary * imaginary


class WebfilmPackageTests(unittest.TestCase):
    def test_package_preserves_versions_assets_and_model_prompt(self):
        with fixture() as root:
            first = root / "第一版 #1.html"
            first.write_text('<!doctype html><title>第一版</title><button>运行</button>', encoding="utf-8")
            second = root / "second"
            second.mkdir()
            (second / "index.html").write_text('<link rel="stylesheet" href="style.css"><p>第二版</p>', encoding="utf-8")
            (second / "style.css").write_bytes(b"p { color: green; }\n")
            prompt = '比较这两个版本。</script><script>这是提示词原文</script>'
            manifest = root / "manifest.json"
            write_json(manifest, {"prompt": prompt, "entries": [{"name": "作品甲", "versions": [
                {"name": "初稿", "work": first.name}, {"name": "修改", "work": "second"}]}]})
            result = package_site(manifest, root / "delivery")
            output = Path(result["output_dir"])
            gallery = result["identity"]["gallery"]
            self.assertEqual(prompt, gallery["prompt"])
            versions = gallery["entries"][0]["versions"]
            self.assertEqual(first.read_bytes(), (output / versions[0]["entrypoint"]).read_bytes())
            self.assertEqual((second / "style.css").read_bytes(), (output / versions[1]["directory"] / "style.css").read_bytes())
            page = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("<iframe", page)
            self.assertIn("encodeURIComponent", page)
            embedded = page.split('<script id="manifest" type="application/json">', 1)[1].split("</script>", 1)[0]
            self.assertEqual(json.loads(embedded), gallery)
            self.assertIn("style.css", versions[1]["sources"])
            self.assertEqual(result["identity"]["manifest"]["sha256"], sha256(manifest))

    def test_package_refuses_existing_originals_and_missing_directory_entrypoint(self):
        with fixture() as root:
            original = root / "work.html"
            original.write_text("original", encoding="utf-8")
            manifest = root / "manifest.json"
            write_json(manifest, {"prompt": "展示", "entries": [{"name": "甲", "versions": [{"name": "一", "work": "work.html"}]}]})
            output = root / "delivery"
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_bytes(b"keep unchanged")
            with self.assertRaises(FileExistsError):
                package_site(manifest, output)
            self.assertEqual(sentinel.read_bytes(), b"keep unchanged")
            empty_work = root / "empty-work"
            empty_work.mkdir()
            write_json(manifest, {"prompt": "展示", "entries": [{"name": "甲", "versions": [{"name": "一", "work": "empty-work"}]}]})
            with self.assertRaisesRegex(ValueError, "no HTML"):
                package_site(manifest, root / "fresh")
            self.assertFalse((root / "fresh").exists())

    def test_upload_template_is_explicitly_illustrative_and_never_overwrites(self):
        with fixture() as root:
            path = upload_template(root / "upload.md")
            body = path.read_text(encoding="utf-8")
            for field in ("标题", "简介", "标签", "置顶评论", "投稿声明"):
                self.assertIn(field, body)
            self.assertIn("虚构示意", body)
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                upload_template(path)
            self.assertEqual(original, path.read_bytes())

    def test_package_accepts_unique_non_index_entry_and_explicit_multiple_entry(self):
        with fixture() as root:
            source = root / "work"
            source.mkdir()
            (source / "model-result.html").write_text("<h1>原样作品</h1>", encoding="utf-8")
            manifest = root / "manifest.json"
            body = {"prompt": "展示原样目录", "entries": [{"name": "模型", "versions": [{"name": "输出", "work": "work"}]}]}
            write_json(manifest, body)
            result = package_site(manifest, root / "unique")
            self.assertTrue(result["identity"]["gallery"]["entries"][0]["versions"][0]["entrypoint"].endswith("model-result.html"))
            (source / "alternative.html").write_text("<h1>另一页</h1>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "alternative.html.*model-result.html"):
                package_site(manifest, root / "ambiguous")
            body["entries"][0]["versions"][0]["entry"] = "alternative.html"
            write_json(manifest, body)
            result = package_site(manifest, root / "explicit")
            self.assertTrue(result["identity"]["gallery"]["entries"][0]["versions"][0]["entrypoint"].endswith("alternative.html"))


@unittest.skipUnless(available_media_tools(), "FFmpeg and FFprobe are required for CPU media integration")
class WebfilmMediaTests(unittest.TestCase):
    def test_short_narration_keeps_its_speed_pads_silence_and_preserves_eligible_picture(self):
        with fixture() as root:
            source, narration = root / "card.mp4", root / "short.wav"
            make_video(source, "red", 440)
            run([tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi",
                 "-i", "sine=frequency=880:sample_rate=48000:duration=0.6", narration])
            timeline = root / "timeline.json"
            write_json(timeline, {"clips": [{"path": "card.mp4", "duration": 1.5,
                                             "narration": {"path": "short.wav", "start": 0.1}}]})
            result = media.compose(timeline, root / "padded.mp4", width=128, height=72, fps=12)
            record = result["identity"]["clips"][0]
            self.assertAlmostEqual(record["narration_source_duration"], 0.6, places=4)
            self.assertAlmostEqual(record["narration_remaining_duration"], 0.5, places=4)
            self.assertAlmostEqual(record["narration_padding_seconds"], 1, places=4)
            self.assertEqual(record["video_processing"], "stream_copy")
            self.assertAlmostEqual(float(probe(result["output"])["format"]["duration"]), 1.5, places=3)
            def audio_samples(start, duration):
                pcm = run([tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-ss", str(start),
                           "-i", result["output"], "-t", str(duration), "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "-"]).stdout
                samples = array("h")
                samples.frombytes(pcm)
                return samples
            voice = audio_samples(0.1, 0.2)
            self.assertGreater(tone_energy(voice, 880), 30 * tone_energy(voice, 440))
            tail = audio_samples(0.9, 0.4)
            self.assertTrue(tail)
            self.assertLess(max(abs(sample) for sample in tail), 4)
            def video_bitstream(path):
                return run([tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-i", path,
                            "-map", "0:v:0", "-an", "-c:v", "copy", "-bsf:v", "h264_mp4toannexb", "-f", "h264", "-"]).stdout
            self.assertEqual(video_bitstream(source), video_bitstream(result["output"]))
            write_json(timeline, {"clips": [{"path": "card.mp4", "duration": 1.5,
                                             "narration": {"path": "short.wav", "start": 0.6}}]})
            with self.assertRaisesRegex(ValueError, "outside its audio duration"):
                media.compose(timeline, root / "invalid.mp4", width=128, height=72, fps=12)

    def test_self_exported_30fps_and_normal_60fps_keep_native_frame_clock(self):
        with fixture() as root:
            exported = root / "model.mp4"
            captured = root / "capture.mp4"
            for path, rate, size in ((exported, 30, "96x72"), (captured, 60, "128x72")):
                run([tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
                     "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration=0.5",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", path])
            timeline = root / "timeline.json"
            write_json(timeline, {"clips": [{"path": "model.mp4", "duration": 0.5, "self_exported": True},
                                             {"path": "capture.mp4", "duration": 0.5}]})
            result = media.compose(timeline, root / "mixed.mp4", width=128, height=72, fps=60)
            identity = result["identity"]
            self.assertEqual([clip["frames"] for clip in identity["clips"]], [15, 30])
            self.assertEqual(identity["clips"][0]["label"], "模型自行导出")
            self.assertEqual(identity["output"]["frame_count"], 45)
            self.assertTrue(identity["settings"]["variable_frame_rate"])
            self.assertAlmostEqual(identity["output"]["duration"], 1, places=4)
            delivered_info = probe(result["output"])
            self.assertAlmostEqual(float(delivered_info["format"]["duration"]), 1, places=3)
            delivered_video = next(stream for stream in delivered_info["streams"] if stream["codec_type"] == "video")
            self.assertAlmostEqual(float(delivered_video["duration"]), 1, places=4)
            clock = media._frame_clock(result["output"])
            self.assertEqual(len(clock), 45)
            self.assertTrue(all(abs((clock[i + 1]["time"] - clock[i]["time"]) - 1 / 30) < 0.00004 for i in range(14)))
            self.assertTrue(all(abs((clock[i + 1]["time"] - clock[i]["time"]) - 1 / 60) < 0.00004 for i in range(15, 44)))
            original = extract_frame(exported, 0.1, root / "original.png")
            delivered = extract_frame(result["output"], 0.1, root / "delivered.png")
            # 4:3 source retains its whole 96x72 picture centered with 16px bars.
            self.assertLess(max(delivered.getpixel((3, 40))), 15)
            self.assertLess(max(delivered.getpixel((124, 40))), 15)
            expected = original.crop((0, 24, 96, 72))
            actual = delivered.crop((16, 24, 112, 72))
            difference = sum(abs(left - right) for a, b in zip(expected.getdata(), actual.getdata()) for left, right in zip(a, b))
            self.assertLess(difference / (96 * 48 * 3), 8)

    def test_compose_changes_layout_burns_timed_subtitles_and_uses_supplied_narration(self):
        with fixture() as root:
            red, blue, narration = root / "red.mp4", root / "blue.mp4", root / "narration.wav"
            make_video(red, "red", 440)
            make_video(blue, "blue", 660)
            run([tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi",
                 "-i", "sine=frequency=880:sample_rate=48000:duration=0.5", narration])
            timeline = root / "timeline.json"
            write_json(timeline, {"clips": [
                {"path": "red.mp4", "duration": 0.5, "narration": "narration.wav",
                 "subtitles": [{"start": 0.15, "end": 0.4, "text": "SUBTITLE"}]},
                {"left": "red.mp4", "right": "blue.mp4", "start": 0.25, "duration": 0.5}]})
            result = media.compose(timeline, root / "final.mp4", width=128, height=72, fps=12)
            output = Path(result["output"])
            information = probe(output)
            self.assertEqual(result["identity"]["output"]["frame_count"], 12)
            self.assertEqual(result["identity"]["output"]["sha256"], sha256(output))
            video = next(s for s in information["streams"] if s["codec_type"] == "video")
            audio = next(s for s in information["streams"] if s["codec_type"] == "audio")
            self.assertEqual((video["width"], video["height"], video["pix_fmt"]), (128, 72, "yuv420p"))
            self.assertEqual((audio["codec_name"], audio["sample_rate"], audio["channels"]), ("aac", "48000", 2))
            paired = extract_frame(output, 0.65, root / "pair.png")
            self.assertGreater(paired.getpixel((32, 36))[0], 200)
            self.assertGreater(paired.getpixel((96, 36))[2], 200)
            before = extract_frame(output, 0.0, root / "before.png")
            during = extract_frame(output, 0.25, root / "during.png")
            white = lambda frame: sum(min(pixel) > 190 for pixel in frame.crop((0, 40, 128, 72)).getdata())
            self.assertGreater(white(during), white(before) + 15)
            pcm = run([tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-ss", "0.10",
                       "-i", output, "-t", "0.20", "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "-"]).stdout
            samples = array("h")
            samples.frombytes(pcm)
            self.assertGreater(tone_energy(samples, 880), 30 * tone_energy(samples, 440))
            self.assertEqual(result["identity"]["audio_normalization"]["passes"], 2)
            self.assertLess(abs(float(result["identity"]["audio_normalization"]["output"]["loudnorm"]["input_i"]) + 14), 1.5)
            self.assertIn(sha256(narration), [s["sha256"] for s in result["identity"]["sources"]])

    def test_compose_silent_source_is_preserved_as_silence_and_bad_inputs_fail(self):
        with fixture() as root:
            source = root / "silent.mp4"
            make_video(source, "green")
            timeline = root / "timeline.json"
            write_json(timeline, {"clips": [{"path": "silent.mp4", "duration": 0.5}]})
            result = media.compose(timeline, root / "silent-output.mp4", width=128, height=72, fps=12)
            self.assertEqual(result["identity"]["clips"][0]["source_audio"], [False])
            self.assertEqual(result["identity"]["audio_normalization"]["output"]["loudnorm"]["input_i"], "-inf")
            with self.assertRaises(FileExistsError):
                media.compose(timeline, root / "silent-output.mp4", width=128, height=72, fps=12)
            write_json(timeline, {"clips": [{"path": "silent.mp4", "duration": 10}]})
            with self.assertRaisesRegex(ValueError, "exceeds source"):
                media.compose(timeline, root / "too-long.mp4", width=128, height=72, fps=12)
            self.assertFalse((root / "too-long.mp4").exists())
            write_json(timeline, {"clips": [{"path": "silent.mp4", "duration": 0.5,
                                              "subtitles": [{"start": 0.3, "end": 0.2, "text": "invalid"}]}]})
            with self.assertRaisesRegex(ValueError, "start < end"):
                media.compose(timeline, root / "bad-cue.mp4", width=128, height=72, fps=12)

    def test_review_keeps_complete_video_and_reports_audio_with_twelve_samples(self):
        with fixture() as root:
            source = root / "source.mp4"
            make_video(source, "purple", 440)
            result = media.review(source, root / "review")
            output = Path(result["output_dir"])
            record = result["identity"]
            self.assertEqual(sha256(source), sha256(output / record["full_video"]))
            self.assertEqual(len(record["frame_samples"]), 12)
            self.assertEqual(record["frame_count"], 18)
            self.assertTrue(record["audio"]["present"])
            with Image.open(output / "contact-sheet.jpg") as image:
                self.assertEqual(image.size, (1920, 888))
            with Image.open(output / "waveform.png") as image:
                self.assertEqual(image.size, (1920, 360))
            with self.assertRaises(FileExistsError):
                media.review(source, output)


if __name__ == "__main__":
    unittest.main()
