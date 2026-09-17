from __future__ import annotations
import base64
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import config
from pipeline import (
    build_scene,
    contracts,
    cleanup,
    workflow,
    fish_native,
    prep,
    preview,
    cover,
    doctor,
    render,
    subtitles,
)
from pipeline.artifact_identity import sha256_file, write_output_record
from pipeline.io_utils import (
    atomic_output,
    publish_bundle,
    project_lock,
    concat_entry,
    encoder_process,
)
from helpers import project_graph, media_probe


class CueTests(unittest.TestCase):
    def resolve(self, text, words=None):
        words = words or [
            {"word": "测试", "start": 0.2, "end": 0.6},
            {"word": "测试", "start": 1.2, "end": 1.6},
        ]
        return ET.fromstring(
            "<svg>" + build_scene.resolve_cues(text, words) + "</svg>"
        )[0]

    def test_single_quote_whitespace_and_existing_delay(self):
        node = self.resolve("<text data-delay='0.1' data-cue = '测试'>测试</text>")
        self.assertEqual(node.get("data-delay"), "0.200")
        self.assertNotIn("data-cue", node.attrib)

    def test_repeated_occurrence_offset(self):
        node = self.resolve(
            '<text data-cue="测试" data-cue-index="2" data-cue-offset="0.1"/>'
        )
        self.assertEqual(node.get("data-delay"), "1.300")

    def test_missing_occurrence_is_auditable(self):
        self.assertIsNotNone(
            self.resolve('<text data-cue="测试" data-cue-index="3"/>').get(
                "data-cue-missing"
            )
        )

    def test_duplicate_attributes_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid static SVG"):
            self.resolve('<g data-delay="1" data-delay="2"/>')

    def test_unsupported_animation_and_invalid_times(self):
        for fragment in (
            '<g data-anim="not-a-runtime-animation"/>',
            '<g data-dur="0"/>',
            '<g data-delay="NaN"/>',
            "<script/>",
            '<g onclick="a()"/>',
        ):
            with self.subTest(fragment=fragment), self.assertRaises(ValueError):
                self.resolve(fragment)

    def test_bad_word_timeline_rejected(self):
        for words in (
            [{"word": "x", "start": True, "end": 1}],
            [{"word": "x", "start": 2, "end": 1}],
            [{"word": "x", "start": 0, "end": float("inf")}],
        ):
            with self.subTest(words=words), self.assertRaises(ValueError):
                build_scene.validate_words(words)

    def test_strict_failure_preserves_previous_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scene.html"
            path.write_text("accepted", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                build_scene.build('<text data-cue="missing"/>', str(path), strict=True)
            self.assertEqual(path.read_text(), "accepted")


class LineageTests(unittest.TestCase):
    def test_complete_lineage_and_actual_media_contract(self):
        with (
            project_graph(),
            mock.patch.object(cleanup, "_ffprobe", side_effect=media_probe),
        ):
            self.assertTrue(cleanup.verify())

    def test_truncated_video_rejected_even_if_av_agree(self):
        with (
            project_graph(),
            mock.patch.object(
                cleanup, "_ffprobe", side_effect=lambda p: media_probe(p, 2, 120)
            ),
        ):
            self.assertFalse(cleanup.verify())

    def test_unknown_stream_duration_is_not_pass(self):
        def probe(path):
            value = media_probe(path)
            if not str(path).endswith(".png"):
                for stream in value["streams"]:
                    stream.pop("duration", None)
            return value

        with project_graph(), mock.patch.object(cleanup, "_ffprobe", side_effect=probe):
            self.assertFalse(cleanup.verify())

    def test_nonzero_stream_start_rejected(self):
        def probe(path):
            value = media_probe(path)
            if not str(path).endswith(".png"):
                value["streams"][1]["start_time"] = ".2"
            return value

        with project_graph(), mock.patch.object(cleanup, "_ffprobe", side_effect=probe):
            self.assertFalse(cleanup.verify())

    def test_all_source_changes_invalidate_delivery(self):
        for relative in (
            "scripts/script_01.txt",
            "raw_audio/audio_01.mp3",
            "srt_data/srt_01.json",
            "scene_html/fragment_01.svg",
            "scene_html/scene_01.html",
            "background.mp4",
            "output/video_track.mp4",
            "output/final_output.mp4",
        ):
            with self.subTest(path=relative), project_graph() as root:
                path = root / relative
                path.write_bytes(path.read_bytes() + b"changed")
                with self.assertRaises((RuntimeError, ValueError)):
                    contracts.require_final()

    def test_wrong_scene_ids_cannot_pass_by_equal_length(self):
        with project_graph() as root:
            (root / "scene_html" / "scene_04.html").rename(
                root / "scene_html" / "scene_03.html"
            )
            with self.assertRaisesRegex(RuntimeError, "indices mismatch"):
                contracts.require_scenes()

    def test_build_checks_audio_before_writing(self):
        with project_graph() as root:
            path = root / "scene_html" / "scene_01.html"
            previous = path.read_bytes()
            (root / "raw_audio" / "audio_01.mp3").write_bytes(b"new-audio")
            with self.assertRaises(RuntimeError):
                workflow.stage_build()
            self.assertEqual(path.read_bytes(), previous)

    def test_sparse_chapter_scene_ids_are_real_ids(self):
        with project_graph() as root:
            self.assertEqual(
                (root / "output" / "chapters.txt").read_text(encoding="utf-8"),
                "00:00 测试\n00:02 末段\n",
            )

    def test_chapter_input_types_and_ranges(self):
        from pipeline.chapters import validate_lines

        for text in (
            "00:00 first\n00:09 beyond\n",
            "00:00 first\n00:02 next\n00:01 previous\n",
            "00:00 first\n00:60 invalid\n",
        ):
            with self.assertRaises(ValueError):
                validate_lines(text, 4)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chapters.json"
            for data in (
                [{"scene": True, "title": "x"}],
                [{"scene": 1, "title": None}],
                [{"scene": 1, "title": "x\ny"}],
            ):
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    workflow._chapter_groups(str(path))

    def test_status_does_not_generate_or_read_secrets(self):
        with (
            project_graph(),
            mock.patch.object(
                config, "get_fish_api_key", side_effect=AssertionError("secret read")
            ),
            mock.patch("os.makedirs", side_effect=AssertionError("write")),
        ):
            result = contracts.status()
            self.assertTrue(result["read_only"])
            self.assertEqual(result["plan"], [])

    def test_cover_and_chapters_content_changes_rejected(self):
        with project_graph() as root:
            (root / "output" / "cover.png").write_bytes(b"changed")
            with self.assertRaises(RuntimeError):
                contracts.require_cover()
            (root / "output" / "chapters.txt").write_text(
                "00:00 okay\n00:50 bad\n", encoding="utf-8"
            )
            with self.assertRaises(RuntimeError):
                contracts.require_chapters()

    def test_global_subtitles_use_sparse_scene_offsets(self):
        with project_graph() as root:
            result = subtitles.export()
            self.assertEqual(result[1][0], 2.2)
            self.assertIn(
                "00:00:02,200",
                (root / "output" / "subtitles.srt").read_text(encoding="utf-8"),
            )


class AtomicAndRuntimeTests(unittest.TestCase):
    def test_failed_atomic_output_preserves_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audio.mp3"
            path.write_bytes(b"accepted")
            with self.assertRaises(RuntimeError):
                with atomic_output(path) as staged:
                    Path(staged).write_bytes(b"partial")
                    raise RuntimeError("injected")
            self.assertEqual(path.read_bytes(), b"accepted")
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)

    def test_bundle_rolls_back_second_replace_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "audio"
            b = root / "identity"
            c = root / "new-audio"
            d = root / "new-identity"
            a.write_bytes(b"old-a")
            b.write_bytes(b"old-b")
            c.write_bytes(b"new-a")
            d.write_bytes(b"new-b")
            original = os.replace

            def replace(source, target):
                if Path(source) == d:
                    raise PermissionError("injected")
                return original(source, target)

            with (
                mock.patch("os.replace", side_effect=replace),
                self.assertRaises(PermissionError),
            ):
                publish_bundle([(c, a), (d, b)])
            self.assertEqual(a.read_bytes(), b"old-a")
            self.assertEqual(b.read_bytes(), b"old-b")

    def test_second_writer_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, project_lock(tmp):
            with self.assertRaises(RuntimeError):
                with project_lock(tmp):
                    pass

    def test_encoder_timeout_reaps_its_child(self):
        with encoder_process(
            [sys.executable, "-c", "import time;time.sleep(10)"], 0.2
        ) as (process, errors):
            process.wait(timeout=5)
            self.assertIsNotNone(process.poll())

    def test_concat_apostrophe_and_unicode(self):
        value = concat_entry("中文 O'Brien.mp3")
        self.assertIn("O'\\''Brien", value)
        with self.assertRaises(ValueError):
            concat_entry("bad\npath.mp3")

    def test_cleanup_dry_run_preserves_unknown_and_known(self):
        with project_graph() as root:
            known = root / "output" / "_chunk_00000.mp4"
            known.write_bytes(b"chunk")
            unknown = root / "output" / "_chunk_manual.mp4"
            unknown.write_bytes(b"original")
            cleanup.cleanup(dry_run=True)
            self.assertTrue(known.exists())
            cleanup.cleanup()
            self.assertFalse(known.exists())
            self.assertTrue(unknown.exists())

    def test_cleanup_failure_is_non_success(self):
        with project_graph() as root:
            (root / "output" / "_chunk_00000.mp4").write_bytes(b"chunk")
            with (
                mock.patch.object(
                    Path, "unlink", side_effect=PermissionError("locked")
                ),
                self.assertRaisesRegex(RuntimeError, "cleanup incomplete"),
            ):
                cleanup.cleanup()

    def test_prep_requires_explicit_mode_and_protects_edited_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            prep.write_scripts(["one", "two"], tmp)
            with self.assertRaises(RuntimeError):
                prep.write_scripts(["three"], tmp)
            prep.write_scripts(["updated"], tmp, mode="replace")
            self.assertFalse((Path(tmp) / "script_02.txt").exists())
            (Path(tmp) / "script_01.txt").write_text("human edit", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                prep.write_scripts(["replacement"], tmp, mode="replace")

    def test_demo_refuses_before_any_initialization(self):
        from pipeline.smoke import run_fixture

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "script.txt"
            path.write_bytes(b"original")
            with self.assertRaises(RuntimeError):
                run_fixture(tmp)
            self.assertEqual(path.read_bytes(), b"original")

    def test_static_doctor_has_no_probe_or_secret_side_effects(self):
        with (
            mock.patch.object(
                doctor, "_run", side_effect=AssertionError("subprocess probe")
            ),
            mock.patch.object(
                doctor, "_playwright_check", side_effect=AssertionError("browser")
            ),
            mock.patch.object(
                config, "get_fish_api_key", side_effect=AssertionError("secret")
            ),
        ):
            checks = doctor.run_checks()
            self.assertTrue(checks)

    def test_relative_asset_changes_render_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scene = root / "scene.html"
            asset = root / "hero.png"
            background = root / "bg.mp4"
            scene.write_text('<svg><image href="hero.png"/></svg>', encoding="utf-8")
            asset.write_bytes(b"a")
            background.write_bytes(b"b")
            with mock.patch.object(config, "BG_VIDEO", str(background)):
                first = render._render_identity_record([str(scene)], [1.0], 60, 60)
                asset.write_bytes(b"changed")
                second = render._render_identity_record([str(scene)], [1.0], 60, 60)
            self.assertNotEqual(first, second)

    def test_cover_escapes_text_and_allows_no_hero(self):
        document = cover._document("A < B & C", "hello", "test", None)
        self.assertIn("A &lt; B &amp; C", document)
        self.assertNotIn("<image", document)

    def test_preview_serialized_data_cannot_close_script(self):
        with project_graph() as root, mock.patch.object(preview, "_ensure_bg"):
            path = root / "scene_html" / "fragment_01.svg"
            path.write_text("<text>&lt;/script&gt;</text>", encoding="utf-8")
            output = preview.build()
            text = Path(output).read_text(encoding="utf-8")
            payload = text.split('id="project">', 1)[1].split("</script>", 1)[0]
            self.assertNotIn("<", payload)
            self.assertIn("<text>", json.loads(payload)["scenes"][0]["fragment"])


class FishTimestampTests(unittest.TestCase):
    def event(self, seq, offset, segments, audio=b"a"):
        return "data: " + json.dumps(
            {
                "audio_base64": base64.b64encode(audio).decode(),
                "chunk_seq": seq,
                "chunk_audio_offset_sec": offset,
                "alignment": {"audio_duration": 1, "segments": segments},
            }
        )

    def test_snapshot_replaced_not_appended_and_offset_applied(self):
        lines = [
            self.event(0, 0, [{"text": "a", "start": 0, "end": 0.3}]),
            self.event(
                0,
                0,
                [
                    {"text": "a", "start": 0, "end": 0.4},
                    {"text": "b", "start": 0.4, "end": 0.8},
                ],
            ),
            self.event(1, 1, [{"text": "c", "start": 0, "end": 0.3}]),
            "data: [DONE]",
        ]
        output = BytesIO()
        words = fish_native.decode(lines, output)
        self.assertEqual(output.getvalue(), b"aaa")
        self.assertEqual([w["word"] for w in words], ["a", "b", "c"])
        self.assertEqual(words[-1]["start"], 1)

    def test_missing_chunk_and_invalid_alignment_rejected(self):
        for lines in (
            [self.event(1, 1, [{"text": "a", "start": 0, "end": 0.3}])],
            [self.event(0, 0, [{"text": "a", "start": 0.8, "end": 0.3}])],
            [],
        ):
            with (
                self.subTest(lines=lines),
                self.assertRaises((ValueError, RuntimeError)),
            ):
                fish_native.decode(lines, BytesIO())

    def test_bad_base64_rejected(self):
        with self.assertRaises(ValueError):
            fish_native.decode(['data: {"audio_base64":"!!!"}'], BytesIO())


if __name__ == "__main__":
    unittest.main()
